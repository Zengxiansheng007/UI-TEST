"""Turn a source-grounded planning request into a validated main Packet."""
import argparse
import json
from pathlib import Path

from ui_test_core.packet_validator import validate_packet


def build(source):
    if not isinstance(source, dict):
        return None, ["source must be a JSON object"]
    steps = source.get("steps")
    if not isinstance(steps, list) or not steps or not all(isinstance(s, dict) for s in steps):
        return None, ["steps: supply ordered actions and observable expected results"]
    assertions = [s for s in steps if s.get("action") == "assert"]
    missing = [f"{s.get('step_id', '?')}.postcondition: supply the expected business result"
               for s in assertions if not str(s.get("postcondition") or "").strip()]
    if not assertions:
        missing.append("steps: identify an assertion and its expected business result")
    for key in ("objective", "scope", "case", "branch", "run", "lineage", "packet_id", "constraints", "history_status"):
        if not source.get(key):
            missing.append(f"{key}: identify the source value")
    lineage = source.get("lineage")
    if not isinstance(lineage, dict) or not lineage.get("source_refs"):
        missing.append("lineage.source_refs: identify the source case or material")
    if missing:
        return None, missing
    packet = {key: source[key] for key in ("packet_id", "objective", "scope", "case", "branch", "run", "lineage", "steps")}
    scope = packet["scope"]
    packet.update(
        schema_version="3.0", packet_type="ui-test-packet", state="plan", next_action="explore",
        risk_level=scope.get("risk_level") if isinstance(scope, dict) else None,
        artifact_refs=source.get("artifact_refs", []),
        evidence_policy={"screenshot_on_ui_change": True, "redaction_required": True},
        retry_policy={"max_attempts": 0, "fallback_allowed": False},
        handoff={"action": "review", "constraints": source["constraints"],
                 "history_status": source["history_status"],
                 **{key: source.get(key, []) for key in ("failure_history", "retry_history", "required_fix_points")}},
    )
    errors = validate_packet(packet)
    return (None, [f"{item['path']} {item['code']}" for item in errors]) if errors else (packet, [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        source = json.loads(args.input.read_text(encoding="utf-8-sig"))
        packet, questions = build(source)
        if questions:
            print(json.dumps({"clarify": questions}, ensure_ascii=True))
            return 2
        with args.output.open("x", encoding="utf-8") as stream:  # Preserve previous plans.
            json.dump(packet, stream, ensure_ascii=False, indent=2)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    print("plan ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
