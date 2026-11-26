"""Deterministic postcondition verification independent of Midscene claims."""

from __future__ import annotations

from typing import Any


def verify_postcondition(observed: dict[str, Any], expected: dict[str, Any], *,
                         ready_context=None, packet=None, session_id=None, page=None, config=None) -> dict[str, Any]:
    checks = []
    for field in ("url", "title", "visible_text", "input_value", "selected", "network_readonly"):
        if field not in expected:
            continue
        if field == "network_readonly":
            from ui_test_core.module_ready import consume_ready_context
            matched = False
            reference = None
            if all((ready_context, packet, session_id, page, config)):
                valid = consume_ready_context(ready_context, packet=packet, session_id=session_id,
                                              page=page, config=config)
                if valid["ok"]:
                    reference = ready_context.get("readonly_network_evidence_ref")
                    matched = bool(reference and reference == expected[field])
            checks.append({"field": field, "evidence_ref": reference, "passed": matched})
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
    return {"passed": passed, "status": "passed" if passed else "failed", "checks": checks, "code": "OK" if passed else "E_POSTCONDITION_MISMATCH"}


def reconcile_midscene(midscene_result: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    model_passed = midscene_result.get("status") == "passed"
    if model_passed and verification.get("passed"):
        return {"status": "passed", "failure_layer": None, "original_model_status": midscene_result.get("status")}
    if model_passed and not verification.get("passed"):
        return {"status": "degraded", "failure_layer": "ai-recognition", "original_model_status": "passed", "verification": verification}
    return {"status": "failed", "failure_layer": midscene_result.get("failure_layer") or "test-asset", "original_model_status": midscene_result.get("status"), "verification": verification}
