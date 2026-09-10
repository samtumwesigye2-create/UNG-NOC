from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


SYSTEMS: dict[str, dict[str, str]] = {
    "101": {"name": "UNG-CORE", "domain": "core-control"},
    "102": {"name": "UNG-ATLAS", "domain": "control-infrastructure"},
    "103": {"name": "UNG-JANUS", "domain": "identity-access"},
    "201": {"name": "UNG-PULSAR", "domain": "data-relay"},
    "202": {"name": "UNG-NEXUS", "domain": "integration-interoperability"},
    "203": {"name": "UNG-HERMES", "domain": "communications"},
    "301": {"name": "UNG-VECTOR", "domain": "warehouse-logistics"},
    "302": {"name": "UGASHIP", "domain": "shipping"},
    "401": {"name": "UGAMAP", "domain": "mapping-routing"},
    "402": {"name": "UNG-ZIPPER", "domain": "destination-grid"},
    "501": {"name": "UNG-AEGIS", "domain": "security-protection"},
    "502": {"name": "UNG-SENTINEL", "domain": "security-operations"},
    "503": {"name": "UNG-VAULT", "domain": "cryptography-secrets"},
    "601": {"name": "UNG-HORUS", "domain": "uas-aerial-operations"},
    "602": {"name": "UNG-CONSTELLATION", "domain": "satellite-operations"},
    "701": {"name": "UNG-ORACLE", "domain": "analysis-decision-support"},
    "702": {"name": "UNG-NOVA", "domain": "data-analytics"},
    "703": {"name": "UNG-APOLLO", "domain": "planning-intelligence"},
    "801": {"name": "UNG-EDGE", "domain": "edge-compute"},
    "802": {"name": "UNG-INTERNALNET", "domain": "internal-network"},
    "901": {"name": "UNG-ORION", "domain": "national-operations-command"},
    "902": {"name": "UNG-NEMSIS", "domain": "emergency-management"},
}


@dataclass(frozen=True)
class Fault:
    fault: str
    title: str
    severity: str
    layer: str
    probable_cause: str
    action: str


FAULTS: dict[str, Fault] = {
    "000": Fault("000", "Healthy", "info", "system", "No fault detected", "No action required"),
    "105": Fault("105", "Starting / not ready", "low", "runtime", "Service is booting but is not ready to accept normal traffic", "Wait for readiness; if persistent, inspect startup logs and dependencies"),
    "101": Fault("101", "DNS resolution failure", "high", "network", "Hostname cannot be resolved", "Check DNS records, resolver and service hostname"),
    "102": Fault("102", "Connection refused", "high", "network", "Target host is reachable but nothing accepts the connection", "Check service process, bind address and listening port"),
    "103": Fault("103", "Connection timeout", "high", "network", "Target did not respond before timeout", "Check routing, firewall, service health and upstream connectivity"),
    "104": Fault("104", "TLS handshake failure", "high", "network", "Certificate, protocol or TLS negotiation failed", "Check certificate validity, hostname and TLS configuration"),
    "201": Fault("201", "Dependency unavailable", "high", "dependency", "Required downstream service is unavailable", "Check named dependency and its health endpoint"),
    "202": Fault("202", "Dependency degraded", "medium", "dependency", "Downstream service responds but is degraded", "Inspect dependency health and recent errors"),
    "301": Fault("301", "Authentication required", "medium", "identity", "Request lacks valid authentication", "Provide a valid JANUS bearer or service token"),
    "302": Fault("302", "Permission denied", "high", "identity", "Principal is authenticated but lacks required permission", "Check JANUS role and permission assignment"),
    "303": Fault("303", "Token invalid or expired", "medium", "identity", "Bearer token cannot be accepted", "Refresh or rotate the token and retry"),
    "401": Fault("401", "Route or endpoint not found", "medium", "application", "Requested API path is not registered", "Verify route prefix, API version and deployment version"),
    "402": Fault("402", "Wrong HTTP method", "medium", "application", "Endpoint exists but request method is incorrect", "Use the method defined by the API contract"),
    "403": Fault("403", "Invalid request payload", "medium", "application", "Payload failed validation or schema checks", "Compare request body with the current API contract"),
    "404": Fault("404", "Wrong listening port", "high", "transport", "Caller is targeting a port different from the service listener", "Compare configured target port with the service listening socket"),
    "405": Fault("405", "Bind-address mismatch", "high", "transport", "Service is listening only on localhost or the wrong interface", "Bind service to the intended interface/address"),
    "406": Fault("406", "Wrong target / environment", "high", "configuration", "Caller is pointing at the wrong host, URL or environment", "Compare production/staging URLs, hostnames and service routing"),
    "500": Fault("500", "Internal service crash", "critical", "application", "The service itself returned an internal server failure", "Inspect application logs, stack trace and the earliest failing dependency"),
    "501": Fault("501", "Database unavailable", "critical", "data", "Application cannot connect to its database", "Check DATABASE_URL, database availability, network and credentials"),
    "502": Fault("502", "Database schema mismatch", "high", "data", "Expected table, column or migration is missing", "Run or reconcile the required database migration"),
    "503": Fault("503", "Cache unavailable", "medium", "data", "Redis/cache dependency is unavailable", "Check cache URL, service state and connectivity"),
    "504": Fault("504", "Fallback / in-memory mode", "high", "data", "Service is running without its intended persistent database or backend", "Restore the configured persistent backend before relying on writes"),
    "601": Fault("601", "Configuration missing", "high", "configuration", "Required environment variable or configuration is absent", "Set the required configuration and restart the service"),
    "602": Fault("602", "Configuration mismatch", "high", "configuration", "Connected systems disagree on URL, port, token, schema or mode", "Compare runtime configuration at both ends"),
    "701": Fault("701", "Service unhealthy", "critical", "runtime", "Health check reports failure", "Inspect service logs and restart only after identifying the failing dependency"),
    "702": Fault("702", "Service not running", "critical", "runtime", "Expected process or container is stopped", "Start the service and inspect startup logs if it exits again"),
    "703": Fault("703", "Resource pressure", "high", "runtime", "Memory, CPU, disk or file descriptors are exhausted", "Inspect resource usage and reduce load or increase capacity"),
    "704": Fault("704", "Crash loop", "critical", "runtime", "Service repeatedly starts and exits", "Inspect earliest startup exception and dependency/configuration failures"),
    "801": Fault("801", "Event delivery failure", "high", "integration", "Event could not be published or acknowledged", "Check NEXUS/PULSAR route, auth and destination status"),
    "802": Fault("802", "Contract/version mismatch", "high", "integration", "Producer and consumer use incompatible message/API versions", "Align contract versions and redeploy the mismatched component"),
    "803": Fault("803", "Queue backlog", "medium", "integration", "Messages are accumulating faster than they are processed", "Inspect consumer health, retries and queue depth"),
    "804": Fault("804", "Data conflict", "high", "integration", "Two writes or ownership/custody updates conflict and require reconciliation", "Hold the conflicting record and reconcile source-of-truth ownership"),
    "905": Fault("905", "Known manual issue", "medium", "operations", "A known issue is recorded that cannot be reliably detected by a live health probe", "Review the recorded issue and clear it only after formal resolution"),
    "901": Fault("901", "Unknown fault", "medium", "unknown", "Symptoms do not match a registered diagnostic rule", "Collect status, logs, target URL, port and dependency health for analysis"),
}


def system_by_name(name: str) -> tuple[str, dict[str, str]] | None:
    needle = name.strip().upper()
    for number, meta in SYSTEMS.items():
        if meta["name"].upper() == needle:
            return number, meta
    return None


def make_code(system_number: str, fault_number: str) -> str:
    # D-Codes deliberately remain separate from UGATU/U-Code transaction identifiers.
    return f"D-{system_number}-{fault_number}"


def decode(code: str) -> dict[str, Any] | None:
    parts = code.strip().upper().split("-")
    # Accept legacy U-prefixed diagnostic codes during migration, but emit D-Codes.
    if len(parts) != 3 or parts[0] not in {"D", "U"}:
        return None
    system_number, fault_number = parts[1], parts[2]
    system = SYSTEMS.get(system_number)
    fault = FAULTS.get(fault_number)
    if not system or not fault:
        return None
    return {
        "code": make_code(system_number, fault_number),
        "legacy_code": f"U-{system_number}-{fault_number}" if parts[0] == "U" else None,
        "system_number": system_number,
        "system": system["name"],
        "domain": system["domain"],
        **asdict(fault),
    }


def diagnose(system_name: str, observation: dict[str, Any]) -> dict[str, Any]:
    system_match = system_by_name(system_name)
    if not system_match:
        return {
            "code": "D-000-901",
            "system": system_name,
            "fault": "901",
            "title": "Unknown system",
            "severity": "medium",
            "probable_cause": "System has not been assigned a UNG diagnostic number",
            "action": "Register the system in the diagnostic system registry",
            "observation": observation,
        }

    system_number, system = system_match
    fault_number = "901"

    expected_port = observation.get("expected_port")
    actual_port = observation.get("actual_port")
    http_status = observation.get("http_status")
    error = str(observation.get("error") or "").lower()
    health = str(observation.get("health") or "").lower()
    database = str(observation.get("database") or "").lower()
    dependency = str(observation.get("dependency") or "").lower()
    resource = str(observation.get("resource") or "").lower()
    mode = str(observation.get("mode") or "").lower()
    target = str(observation.get("target_state") or "").lower()
    conflict = str(observation.get("conflict") or "").lower()

    if expected_port is not None and actual_port is not None and str(expected_port) != str(actual_port):
        fault_number = "404"
    elif mode in {"fallback", "in-memory", "in_memory", "memory"} or "in-memory" in error or "fallback" in error:
        fault_number = "504"
    elif target in {"wrong", "staging", "wrong_environment", "wrong-target"}:
        fault_number = "406"
    elif conflict in {"true", "yes", "collision", "conflict"}:
        fault_number = "804"
    elif "name or service not known" in error or "dns" in error or "resolve" in error:
        fault_number = "101"
    elif "connection refused" in error:
        fault_number = "102"
    elif "timeout" in error or "timed out" in error:
        fault_number = "103"
    elif "ssl" in error or "tls" in error or "certificate" in error:
        fault_number = "104"
    elif http_status == 401:
        fault_number = "301"
    elif http_status == 403:
        fault_number = "302"
    elif http_status == 404:
        fault_number = "401"
    elif http_status == 405:
        fault_number = "402"
    elif http_status == 422:
        fault_number = "403"
    elif http_status is not None and 500 <= int(http_status) < 600:
        fault_number = "500"
    elif database in {"down", "unavailable", "failed", "disconnected"}:
        fault_number = "501"
    elif database in {"schema_mismatch", "migration_missing", "wrong_schema"}:
        fault_number = "502"
    elif dependency in {"down", "unavailable", "failed"}:
        fault_number = "201"
    elif dependency == "degraded":
        fault_number = "202"
    elif resource in {"memory", "cpu", "disk", "fd", "pressure", "exhausted"}:
        fault_number = "703"
    elif health in {"starting", "booting", "not_ready", "not-ready"}:
        fault_number = "105"
    elif health in {"down", "unhealthy", "failed", "offline"}:
        fault_number = "701"
    elif health in {"ok", "healthy", "online", "ready"}:
        fault_number = "000"

    fault = FAULTS[fault_number]
    return {
        "code": make_code(system_number, fault_number),
        "system_number": system_number,
        "system": system["name"],
        "domain": system["domain"],
        **asdict(fault),
        "observation": observation,
    }


def catalog() -> dict[str, Any]:
    return {
        "format": "D-SSS-FFF",
        "description": "SSS identifies the UNG system; FFF identifies the diagnosed fault. D-Codes are intentionally separate from UGATU/U-Code transaction identifiers.",
        "legacy_diagnostic_format": "U-SSS-FFF accepted for decode during migration only",
        "systems": SYSTEMS,
        "faults": {number: asdict(fault) for number, fault in FAULTS.items()},
    }
