"""Deterministic postcondition verification independent of Midscene claims."""

from __future__ import annotations

from typing import Any

CURRENT_MISSING = "E_CURRENT_NETWORK_EVIDENCE_MISSING"


def recorded_response_ref(fact, owner):
    """Bind a redacted natural response to its original run, session and step."""
    if not isinstance(fact, dict) or not isinstance(owner, dict):
        return None
    identity = ("run_id", "case_id", "branch_id", "attempt_ref", "step_id", "session_id")
    if not all(isinstance(owner.get(k), str) and owner[k] and fact.get(k) == owner[k] for k in identity):
        return None
    from ui_test_core.module_ready import instant
    try:
        if not instant(owner["started_at"]) <= instant(fact["observed_at"]) <= instant(owner["ended_at"]):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    if (fact.get("source") != "page-response" or fact.get("method") not in ("GET", "HEAD")
            or type(fact.get("status")) is not int or not 200 <= fact["status"] < 300
            or not all(fact.get(k) is True for k in ("request_matched", "response_matched", "business_success"))):
        return None
    ref = fact.get("evidence_ref")
    return ref if isinstance(ref, str) and ref.strip() else None


def verify_postcondition(observed: dict[str, Any], expected: dict[str, Any], *,
                         ready_context=None, packet=None, session_id=None, page=None, config=None,
                         recorded_owner=None, network_evidence=None) -> dict[str, Any]:
    checks = []
    for field in ("url", "title", "visible_text", "input_value", "selected", "network_readonly"):
        if field not in expected:
            continue
        if field == "network_readonly":
            from ui_test_core.module_ready import consume_ready_context
            mode = "recorded" if recorded_owner is not None else "live"
            reference = recorded_response_ref(network_evidence, recorded_owner)
            if mode == "live" and all((ready_context, packet, session_id, page, config)):
                from ui_test_core.case_contracts import canonical_hash
                captures = getattr(page, "_ui_test_response_captures", {})
                if (canonical_hash(ready_context) in captures and not page.is_closed()
                        and all(config.get(k) for k in ("target_url", "login_selector", "module_id"))
                        and packet.get("run", {}).get("run_id")):
                    valid = consume_ready_context(ready_context, packet=packet, session_id=session_id,
                                                  page=page, config=config)
                    if valid["ok"]:
                        reference = ready_context.get("readonly_network_evidence_ref")
            matched = bool(reference and reference == expected[field])
            checks.append({"field": field, "evidence_ref": reference, "mode": mode, "passed": matched,
                           "code": "OK" if matched else CURRENT_MISSING})
            continue
        actual = observed.get(field)
        wanted = expected[field]
        if field == "visible_text" and isinstance(wanted, list):
            passed = all(item in (actual or []) for item in wanted)
        elif field == "url" and isinstance(wanted, str):
            passed = wanted in str(actual or "")
        else:
            passed = actual == wanted
        checks.append({"field": field, "passed": passed})
    if not checks:
        return {"passed": False, "status": "failed", "code": "E_EVIDENCE_MISSING", "checks": []}
    passed = all(item["passed"] for item in checks)
    failed_code = next((check["code"] for check in checks if not check["passed"] and "code" in check),
                       "E_POSTCONDITION_MISMATCH")
    return {"passed": passed, "status": "passed" if passed else "failed", "checks": checks, "code": "OK" if passed else failed_code}


def reconcile_midscene(midscene_result: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    model_passed = midscene_result.get("status") == "passed"
    if model_passed and verification.get("passed"):
        return {"status": "passed", "failure_layer": None, "original_model_status": midscene_result.get("status")}
    if model_passed and not verification.get("passed"):
        return {"status": "degraded", "failure_layer": "ai-recognition", "original_model_status": "passed", "verification": verification}
    return {"status": "failed", "failure_layer": midscene_result.get("failure_layer") or "test-asset", "original_model_status": midscene_result.get("status"), "verification": verification}
