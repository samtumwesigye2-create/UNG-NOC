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

from diagnostics import diagnose

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
    url = base_url.rstrip("/") + "/health"
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


def _append_history(report: dict[str, Any]) -> None:
    try:
        with HISTORY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, separators=(",", ":"), default=str) + "\n")
    except Exception:
        pass


def scan_all() -> dict[str, Any]:
    configured = targets()
    results = [probe(system, url) for system, url in configured.items()]
    with LOCK:
        LATEST.clear()
        LATEST.update({item["system"]: item for item in results})
    faults = [item for item in results if item.get("fault") != "000"]
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    faults.sort(key=lambda x: severity_rank.get(str(x.get("severity")), 0), reverse=True)
    report = {
        "status": "faults_detected" if faults else "healthy",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "configured_systems": len(configured),
        "fault_count": len(faults),
        "faults": faults,
        "systems": results,
    }
    _append_history(report)
    return report


def latest() -> dict[str, Any]:
    with LOCK:
        systems = list(LATEST.values())
    faults = [item for item in systems if item.get("fault") != "000"]
    return {
        "status": "faults_detected" if faults else ("healthy" if systems else "not_scanned"),
        "fault_count": len(faults),
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
