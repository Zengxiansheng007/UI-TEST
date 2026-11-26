"""Review a single action against its declared expected result using existing observations."""
import argparse
import json
from pathlib import Path

from ui_test_core.strict_json import load_strict_json
from ui_test_core.verifier import verify_postcondition


def review_action(source):
    if not isinstance(source, dict):
        raise ValueError("E_VERIFY_INPUT_OBJECT")
    for field in ("action", "evidence_ref"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise ValueError("E_VERIFY_MISSING:" + field)
    expected = source.get("expected")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("E_STEP_POSTCONDITION_MISSING")
    supported = {"url", "title", "visible_text", "input_value", "selected", "network_readonly"}
    for field, value in expected.items():
        if field not in supported:
            raise ValueError("E_VERIFY_FIELD:" + field)
        if value is None or value == [] or (field != "input_value" and value == ""):
            raise ValueError("E_STEP_POSTCONDITION_MISSING:" + field)
    if not isinstance(source.get("observed"), dict):
        raise ValueError("E_VERIFY_MISSING:observed")
    primary = verify_postcondition(source["observed"], expected)
    result = dict(action=source["action"], primary=primary, evidence_ref=source["evidence_ref"],
                  assertion_ref="#/expected", assertion_fields=list(expected), status=primary["status"], repeat_action=False)
    fallback = source.get("fallback")
    if primary["passed"] or fallback is None:
        return result
    if not isinstance(fallback, dict) or not isinstance(fallback.get("observed"), dict):
        raise ValueError("E_VERIFY_MISSING:fallback.observed")
    for key in ("reason", "evidence_ref"):
        if not isinstance(fallback.get(key), str) or not fallback[key].strip():
            raise ValueError("E_VERIFY_MISSING:fallback." + key)
    checked = verify_postcondition(fallback["observed"], expected)
    result["fallback"] = dict(checked, evidence_ref=fallback["evidence_ref"], reason=fallback["reason"])
    result["status"] = "degraded" if checked["passed"] else "failed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = review_action(load_strict_json(args.input))
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=True))
    return int(result["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
