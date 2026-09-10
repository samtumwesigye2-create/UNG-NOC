from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from diagnostics import FAULTS, SYSTEMS, diagnose, make_code

DEFAULT_TARGETS = {
    "UNG-ATLAS": "https://ung-atlas-production.up.railway.app",
    "UNG-JANUS": "https://ung-iam-production.up.railway.app",
    "UNG-PULSAR": "https://ung-pulsar-production.up.railway.app",
    "UNG-NEXUS": "https://ung-nexus-production.up.railway.app",
    "UGAMAP": "https://uganda-grid-api-clean-production.up.railway.app",
    "UNG-ZIPPER": "https://ung-zipper-production.up.railway.app",
}

LATEST: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()
STOP = threading.Event()
THREAD: threading.Thread | None = None
HISTORY_PATH = Path(os.getenv("ORION_DIAGNOSTIC_HISTORY", "diagnostics_history.jsonl"))
KNOWN_ISSUES_PATH = Path(os.getenv("ORION_KNOWN_ISSUES_PATH", "known_issues.json"))
RETRY_ATTEMPTS = max(1, int(os.getenv("ORION_MONITOR_RETRIES", "3")))
RETRY_DELAY_SECONDS = max(0.0, float(os.getenv("ORION_MONITOR_RETRY_DELAY_SECONDS", "1.5")))


def _env_key(system: str) -> str:
    return system.replace("-", "_").replace(" ", "_") + "_BASE_URL"


def targets() -> dict[str, str]:
    result: dict[str, str] = {}
    for system, default in DEFAULT_TARGETS.items():
        value = os.getenv(_env_key(system), default).strip().rstrip("/")
        if value:
            result[system] = value
    for system in ["UNG-CORE", "UNG-HERMES", "UNG-VECTOR", "UGASHIP", "UNG-AEGIS", "UNG-SENTINEL", "UNG-VAULT", "UNG-HORUS", "UNG-CONSTELLATION", "UNG-ORACLE", "UNG-NOVA", "UNG-APOLLO", "UNG-EDGE", "UNG-INTERNALNET", "UNG-NEMSIS"]:
        value = os.getenv(_env_key(system), "").strip().rstrip("/")
        if value:
            result[system] = value
    return result


def _health_value(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("status", "health", "state"):
            value = payload.get(key)
            if value is not None:
                return str(value).lower()
        if payload.get("ok") is True or payload.get("online") is True:
            return "ok"
    return "ok"


def _probe_once(system: str, base_url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    path = "/api/telemetry/current" if system == "UNG-INTERNALNET" else "/health"
    url = base_url.rstrip("/") + path
    observation: dict[str, Any] = {"target": base_url}
    payload: Any = None
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "UNG-ORION-Diagnostics/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            lower_body = body.lower()
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {"raw": body[:500]}
            observation["http_status"] = response.status
            observation["health"] = _health_value(payload)
            if "in-memory" in lower_body or "fallback" in lower_body:
                observation["mode"] = "fallback"
            if system == "UNG-INTERNALNET" and isinstance(payload, dict):
                alarms = payload.get("alarms") or []
                if alarms:
                    first = alarms[0]
                    code = str(first.get("d_code") or first.get("code") or "")
                    parts = code.split("-")
                    if len(parts) == 3:
                        observation["internalnet_fault"] = parts[2]
                        observation["internalnet_alarm"] = first
                        observation["health"] = "degraded"
    except urllib.error.HTTPError as exc:
        observation["http_status"] = exc.code
        observation["error"] = f"HTTP {exc.code}: {exc.reason}"
        observation["health"] = "down" if exc.code >= 500 else "unknown"
    except Exception as exc:
        observation["error"] = str(exc)
        observation["health"] = "offline"
    observation["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    observation["checked_at"] = datetime.now(timezone.utc).isoformat()
    result = diagnose(system, observation)
    if system == "UNG-INTERNALNET" and observation.get("internalnet_fault") in FAULTS:
        fault_id = observation["internalnet_fault"]
        f = FAULTS[fault_id]
        result.update({
            "code": make_code("802", fault_id),
            "fault": fault_id,
            "title": f.title,
            "severity": f.severity,
            "layer": f.layer,
            "probable_cause": f.probable_cause,
            "action": f.action,
        })
    result["target"] = base_url
    result["payload"] = payload
    return result


def probe(system: str, base_url: str, timeout: float = 5.0) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        result = _probe_once(system, base_url, timeout)
        result["attempt"] = attempt
        last = result
        if result.get("fault") in {"000", "105"}:
            return result
        if attempt < RETRY_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)
    assert last is not None
    last["retry_exhausted"] = RETRY_ATTEMPTS > 1
    last["attempts"] = RETRY_ATTEMPTS
    return last


def _load_known_issues() -> list[dict[str, Any]]:
    try:
        data = json.loads(KNOWN_ISSUES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw = data.get("issues", {}) if isinstance(data, dict) else {}
    out: list[dict[str, Any]] = []
    for system_number, entries in raw.items():
        system = SYSTEMS.get(str(system_number))
        if not system or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            fault_id = str(entry.get("fault") or "905")
            if fault_id not in FAULTS:
                fault_id = "905"
            fault = FAULTS[fault_id]
            out.append({
                "code": make_code(str(system_number), fault_id),
                "system_number": str(system_number),
                "system": system["name"],
                "domain": system["domain"],
                "fault": fault_id,
                "title": fault.title,
                "severity": str(entry.get("severity") or fault.severity),
                "layer": fault.layer,
                "probable_cause": str(entry.get("note") or fault.probable_cause),
                "action": str(entry.get("action") or fault.action),
                "manual": True,
                "recorded_at": entry.get("recorded_at"),
            })
    return out


def known_issues() -> dict[str, Any]:
    issues = _load_known_issues()
    return {"count": len(issues), "issues": issues}


def _append_history(report: dict[str, Any]) -> None:
    try:
        with HISTORY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, separators=(",", ":"), default=str) + "\n")
    except Exception:
        pass


def history(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    try:
        lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        lines = []
    reports: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            reports.append(json.loads(line))
        except Exception:
            continue
    return {"count": len(reports), "limit": limit, "reports": reports}


def scan_all() -> dict[str, Any]:
    configured = targets()
    results = [probe(system, url) for system, url in configured.items()]
    with LOCK:
        LATEST.clear()
        LATEST.update({item["system"]: item for item in results})
    live_faults = [item for item in results if item.get("fault") != "000"]
    manual_faults = _load_known_issues()
    faults = live_faults + manual_faults
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    faults.sort(key=lambda x: severity_rank.get(str(x.get("severity")), 0), reverse=True)
    report = {
        "status": "faults_detected" if faults else "healthy",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "configured_systems": len(configured),
        "fault_count": len(faults),
        "live_fault_count": len(live_faults),
        "manual_issue_count": len(manual_faults),
        "faults": faults,
        "systems": results,
    }
    _append_history(report)
    return report


def latest() -> dict[str, Any]:
    with LOCK:
        systems = list(LATEST.values())
    live_faults = [item for item in systems if item.get("fault") != "000"]
    manual_faults = _load_known_issues()
    faults = live_faults + manual_faults
    return {
        "status": "faults_detected" if faults else ("healthy" if systems else "not_scanned"),
        "fault_count": len(faults),
        "live_fault_count": len(live_faults),
        "manual_issue_count": len(manual_faults),
        "faults": faults,
        "systems": systems,
    }


def _loop(interval: int) -> None:
    while not STOP.is_set():
        try:
            scan_all()
        except Exception:
            pass
        STOP.wait(interval)


def start_background() -> None:
    global THREAD
    if os.getenv("ORION_MONITOR_ENABLED", "1").lower() not in {"1", "true", "yes", "on"}:
        return
    if THREAD and THREAD.is_alive():
        return
    interval = max(15, int(os.getenv("ORION_MONITOR_INTERVAL_SECONDS", "30")))
    STOP.clear()
    THREAD = threading.Thread(target=_loop, args=(interval,), name="orion-diagnostic-monitor", daemon=True)
    THREAD.start()


def stop_background() -> None:
    STOP.set()
