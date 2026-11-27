"""Single control-plane route decision shared by current and legacy entrypoints."""

from __future__ import annotations

from typing import Any

from .packet_validator import validate_packet
from .problem_details import from_validation_errors
from .suite import selected_suite


def select_packet(packet: dict[str, Any], source: str = "ui-test", *, historical_name=False) -> dict[str, Any]:
    """Validate first, then select one installed capability at the highest matching priority."""
    errors = validate_packet(packet)
    if errors:
        return {
            "ok": False,
            "route": None,
            "deprecated": source == "ui-test-system",
            "problem": from_validation_errors(errors).as_dict(),
        }
    suite = selected_suite()
    entries = [row for row in suite.catalog["entries"]
               if row["kind"] == "capability" and row["name"] != "ui-test"]
    candidates = []
    for field in ("next_action", "state"):
        candidates = [row for row in entries if packet[field] in row.get("route", {}).get(field, [])]
        if candidates:
            break
    if len(candidates) != 1:
        ambiguous = bool(candidates)
        return {
            "ok": False,
            "route": None,
            "deprecated": source == "ui-test-system",
            "problem": {
                "type": "https://codex.local/problems/e_route_" + ("ambiguous" if ambiguous else "unknown"),
                "title": f"Multiple capabilities match {field}" if ambiguous else "No matching child capability",
                "status": 422,
                "code": "E_ROUTE_AMBIGUOUS" if ambiguous else "E_ROUTE_UNKNOWN",
                "candidates": [item["name"] for item in candidates],
            },
        }
    entry, = candidates
    return {
        "ok": True,
        "route": (entry.get("aliases") or [entry["name"]])[0] if historical_name else entry["name"],
        "skill": str(suite.skill_path(entry["name"])),
        "matched_by": field,
        "packet_schema_version": packet["schema_version"],
        "packet_id": packet["packet_id"],
        "deprecated": source == "ui-test-system",
        "replacement": "ui-test" if source == "ui-test-system" else None,
        "payload_forwarded": True,
    }


def route_packet(packet: dict[str, Any], source: str = "ui-test") -> dict[str, Any]:
    """Preserve the historical callback name for callers of the original Python API."""
    return select_packet(packet, source, historical_name=True)


def legacy_route_decision(packet: dict[str, Any]) -> dict[str, Any]:
    decision = route_packet(packet, source="ui-test-system")
    decision["payload_forwarded"] = False
    decision["route"] = "ui-test"
    decision["status_code"] = "deprecated"
    return decision
