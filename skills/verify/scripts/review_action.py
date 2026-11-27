"""Review a single action against its declared expected result using existing observations."""
import argparse
import hashlib
import json
from pathlib import Path

from ui_test_core.strict_json import load_strict_json, loads_strict
from ui_test_core.verifier import verify_postcondition


def review_action(source, *, page=None, packet=None, session_id=None, config=None, ready_context=None,
                  recorded_owner=None, network_evidence=None):
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
    binding = dict(page=page, packet=packet, session_id=session_id, config=config, ready_context=ready_context,
                   recorded_owner=recorded_owner, network_evidence=network_evidence)
    primary = verify_postcondition(source["observed"], expected, **binding)
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
    checked = verify_postcondition(fallback["observed"], expected, **binding)
    result["fallback"] = dict(checked, evidence_ref=fallback["evidence_ref"], reason=fallback["reason"])
    result["status"] = "degraded" if checked["passed"] else "failed"
    return result


def review_recorded_step(observations, check):
    """Resolve the assertion against one step in the selected exploration delivery."""
    keys = ("case_id", "branch_id", "attempt_ref")
    matches = [(i, j, case, step) for i, case in enumerate(observations["cases"])
               if all(case[key] == check[key] for key in keys) and case["status"] in {"observed", "blocked"}
               for j, step in enumerate(case["steps"]) if step["step_id"] == check["step_id"]]
    if len(matches) != 1:
        raise ValueError("E_WORKFLOW_OBSERVATION_IDENTITY: " + check["case_id"] + "/" + check["step_id"])
    i, j, case, step = matches[0]
    if step.get("status", "passed") not in ("passed", "observed"):
        raise ValueError("E_WORKFLOW_OBSERVATION_STATUS: " + check["step_id"])
    observed = step.get("observed")
    if observed is None and isinstance(step.get("actual_result"), str):
        observed = {"visible_text": [step["actual_result"]]}
    owner = {key: case[key] for key in keys}
    owner.update(step_id=step["step_id"], run_id=observations.get("run_id"),
                 session_id=case.get("session_id", observations.get("session_id", step.get("session_id"))))
    if (observations.get("stage") != "midscene" or case.get("run_id") != owner["run_id"]
            or any(step.get(k, v) != v or check.get(k, v) != v for k, v in owner.items())):
        owner = {}  # Conflicting step, caller or run identities disqualify the response.
    owner.update(started_at=observations.get("started_at"), ended_at=observations.get("ended_at"))
    if observed is None and "network_readonly" in check["expected"]:
        observed = {}
    return review_action(dict(action=step["action"], evidence_ref=f"/cases/{i}/steps/{j}",
                              expected=check["expected"], observed=observed),
                         recorded_owner=owner, network_evidence=step.get("network_evidence"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--observations", type=Path, help="Original exploration observations for a recorded check")
    parser.add_argument("--observations-sha256", help="Expected digest of the selected run's observations")
    args = parser.parse_args()
    try:
        source = load_strict_json(args.input)
        if args.observations is not None or args.observations_sha256 is not None:
            if not args.observations or not args.observations_sha256:
                raise ValueError("E_VERIFY_OBSERVATIONS_BINDING")
            raw = args.observations.read_bytes()
            if hashlib.sha256(raw).hexdigest() != args.observations_sha256 or not source.get("run_id") or not source.get("session_id"):
                raise ValueError("E_CURRENT_NETWORK_EVIDENCE_MISSING")
            result = review_recorded_step(loads_strict(raw.decode("utf8")), source)
        else:
            result = review_action(source)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=True))
    return int(result["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
