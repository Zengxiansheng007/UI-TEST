from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List


ALLOWED_STAGES = {f"CP{i}" for i in range(7)}
ALLOWED_STATUS = {"passed", "failed", "degraded", "blocked"}
ALLOWED_RISK_LEVELS = {"R0", "R1", "R2", "R3"}
ALLOWED_FAILURE_LAYERS = {
    "ui",
    "api",
    "task",
    "downstream",
    "data",
    "env",
    "locator",
    "model",
    "governance",
}
ALLOWED_FAILURE_TYPES = {
    "locator_drift",
    "missing_field",
    "timeout",
    "false_positive",
    "stale_source",
    "permission_denied",
    "cleanup_failed",
    "contract_mismatch",
    "route_mismatch",
    "data_stale",
    "unknown",
}
MUTATING_ACTIONS = {
    "add",
    "associate",
    "create",
    "delete",
    "deploy",
    "publish",
    "approve",
    "submit",
    "update",
    "write",
}


class CheckpointValidationError(ValueError):
    pass


def _canonical(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canonical(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_canonical(i) for i in obj]
    return obj


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(_canonical(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _require_map(payload: Any, context: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise CheckpointValidationError(f"{context} must be an object")
    return payload


def _require_fields(payload: Dict[str, Any], fields: Iterable[str], context: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise CheckpointValidationError(f"missing required field(s) in {context}: {', '.join(missing)}")


def _require_non_empty_string(value: Any, context: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CheckpointValidationError(f"{context} must be a non-empty string")


def _require_string_list(value: Any, context: str) -> None:
    if not isinstance(value, list) or len(value) == 0:
        raise CheckpointValidationError(f"{context} must be a non-empty list")
    for item in value:
        _require_non_empty_string(item, context)


def _validate_stage_and_id(checkpoint: Dict[str, Any]) -> None:
    stage = checkpoint["stage"]
    if stage not in ALLOWED_STAGES:
        raise CheckpointValidationError(f"stage must be one of {sorted(ALLOWED_STAGES)}")
    checkpoint_id = checkpoint["checkpoint_id"]
    _require_non_empty_string(checkpoint_id, "checkpoint_id")
    if not str(checkpoint_id).startswith(stage):
        raise CheckpointValidationError("checkpoint_id must start with stage prefix")


def _validate_source_baseline(source_baseline: Dict[str, Any]) -> None:
    _require_fields(
        source_baseline,
        [
            "prd_version",
            "figma_version",
            "design_version",
            "api_version",
            "code_branch",
            "environment_ref",
            "captured_at",
        ],
        "source_baseline",
    )
    for key in [
        "prd_version",
        "figma_version",
        "design_version",
        "api_version",
        "code_branch",
        "environment_ref",
        "captured_at",
    ]:
        _require_non_empty_string(source_baseline[key], f"source_baseline.{key}")


def _validate_execution_context(execution_context: Dict[str, Any]) -> None:
    _require_fields(
        execution_context,
        [
            "base_url",
            "route",
            "role_account_type",
            "environment_ref",
            "browser_profile",
            "viewport",
            "run_mode",
            "allowed_actions",
            "forbidden_actions",
            "test_data_ref",
            "auth_ref",
            "cleanup_scope",
        ],
        "execution_context",
    )
    for key in ["base_url", "route", "role_account_type", "environment_ref", "browser_profile", "run_mode", "test_data_ref", "auth_ref", "cleanup_scope"]:
        _require_non_empty_string(execution_context[key], f"execution_context.{key}")
    viewport = _require_map(execution_context["viewport"], "execution_context.viewport")
    _require_fields(viewport, ["width", "height"], "execution_context.viewport")
    if not isinstance(viewport["width"], int) or viewport["width"] <= 0:
        raise CheckpointValidationError("execution_context.viewport.width must be a positive integer")
    if not isinstance(viewport["height"], int) or viewport["height"] <= 0:
        raise CheckpointValidationError("execution_context.viewport.height must be a positive integer")
    _require_string_list(execution_context["allowed_actions"], "execution_context.allowed_actions")
    _require_string_list(execution_context["forbidden_actions"], "execution_context.forbidden_actions")
    if set(execution_context["allowed_actions"]) & set(execution_context["forbidden_actions"]):
        raise CheckpointValidationError("allowed_actions and forbidden_actions must not overlap")


def _validate_depends_on(depends_on: Any) -> None:
    if not isinstance(depends_on, list):
        raise CheckpointValidationError("depends_on must be a list")
    for item in depends_on:
        dep = _require_map(item, "depends_on item")
        _require_fields(dep, ["checkpoint_id", "dependency_type", "impact"], "depends_on item")
        _require_non_empty_string(dep["checkpoint_id"], "depends_on.checkpoint_id")
        _require_non_empty_string(dep["dependency_type"], "depends_on.dependency_type")
        _require_non_empty_string(dep["impact"], "depends_on.impact")


def _validate_steps(steps: Any) -> None:
    if steps is None:
        return
    if not isinstance(steps, list):
        raise CheckpointValidationError("steps must be a list")
    for step in steps:
        item = _require_map(step, "steps item")
        _require_fields(item, ["id", "name", "action", "verification", "evidence_refs"], "steps item")
        for key in ["id", "name", "action", "verification"]:
            _require_non_empty_string(item[key], f"steps.{key}")
        _require_string_list(item["evidence_refs"], "steps.evidence_refs")


def _validate_validate(validate: Dict[str, Any]) -> None:
    _require_fields(validate, ["ui", "api", "task", "downstream", "schema"], "validate")
    for key in ["ui", "api", "task", "downstream", "schema"]:
        _require_string_list(validate[key], f"validate.{key}")


def _validate_evidence(evidence: Dict[str, Any]) -> None:
    _require_fields(evidence, ["artifacts", "summary"], "evidence")
    _require_non_empty_string(evidence["summary"], "evidence.summary")
    if not isinstance(evidence["artifacts"], list) or len(evidence["artifacts"]) == 0:
        raise CheckpointValidationError("evidence.artifacts must be a non-empty list")
    for artifact in evidence["artifacts"]:
        item = _require_map(artifact, "evidence.artifacts item")
        _require_fields(item, ["type", "path"], "evidence.artifacts item")
        _require_non_empty_string(item["type"], "evidence.artifacts.type")
        _require_non_empty_string(item["path"], "evidence.artifacts.path")


def _validate_governance(governance: Dict[str, Any]) -> None:
    _require_fields(governance, ["owner", "reviewer", "approved_by", "decision", "decision_reason"], "governance")
    for key in ["owner", "reviewer", "approved_by", "decision", "decision_reason"]:
        _require_non_empty_string(governance[key], f"governance.{key}")


def _validate_promotion_gate(promotion_gate: Dict[str, Any]) -> None:
    _require_fields(
        promotion_gate,
        ["candidate_type", "pass_count", "required_pass_count", "confidence", "blocked_reasons"],
        "promotion_gate",
    )
    if promotion_gate["candidate_type"] not in {"playwright", "hybrid", "manual"}:
        raise CheckpointValidationError("promotion_gate.candidate_type must be playwright, hybrid, or manual")
    if not isinstance(promotion_gate["pass_count"], int) or promotion_gate["pass_count"] < 0:
        raise CheckpointValidationError("promotion_gate.pass_count must be a non-negative integer")
    if not isinstance(promotion_gate["required_pass_count"], int) or promotion_gate["required_pass_count"] < 0:
        raise CheckpointValidationError("promotion_gate.required_pass_count must be a non-negative integer")
    if not isinstance(promotion_gate["confidence"], (int, float)) or not (0 <= promotion_gate["confidence"] <= 1):
        raise CheckpointValidationError("promotion_gate.confidence must be between 0 and 1")
    if not isinstance(promotion_gate["blocked_reasons"], list):
        raise CheckpointValidationError("promotion_gate.blocked_reasons must be a list")


def _validate_staleness_policy(staleness_policy: Dict[str, Any]) -> None:
    _require_fields(staleness_policy, ["dependency_categories", "validation_result"], "staleness_policy")
    _require_string_list(staleness_policy["dependency_categories"], "staleness_policy.dependency_categories")
    _require_non_empty_string(staleness_policy["validation_result"], "staleness_policy.validation_result")


def _validate_cleanup_policy(cleanup_policy: Dict[str, Any]) -> None:
    _require_fields(cleanup_policy, ["required_for_write", "scope", "verification"], "cleanup_policy")
    if not isinstance(cleanup_policy["required_for_write"], bool):
        raise CheckpointValidationError("cleanup_policy.required_for_write must be boolean")
    _require_non_empty_string(cleanup_policy["scope"], "cleanup_policy.scope")
    _require_non_empty_string(cleanup_policy["verification"], "cleanup_policy.verification")


def _validate_failure_attribution(failure_attribution: Dict[str, Any]) -> None:
    _require_fields(
        failure_attribution,
        ["layer", "failure_type", "root_cause_id", "confidence", "evidence_refs", "impact_scope", "action_taken", "next_step"],
        "failure_attribution",
    )
    if failure_attribution["layer"] not in ALLOWED_FAILURE_LAYERS:
        raise CheckpointValidationError("invalid failure_attribution.layer")
    if failure_attribution["failure_type"] not in ALLOWED_FAILURE_TYPES:
        raise CheckpointValidationError("invalid failure_attribution.failure_type")
    _require_non_empty_string(failure_attribution["root_cause_id"], "failure_attribution.root_cause_id")
    if not isinstance(failure_attribution["confidence"], (int, float)) or not (0 <= failure_attribution["confidence"] <= 1):
        raise CheckpointValidationError("failure_attribution.confidence must be between 0 and 1")
    _require_string_list(failure_attribution["evidence_refs"], "failure_attribution.evidence_refs")
    for key in ["impact_scope", "action_taken", "next_step"]:
        _require_non_empty_string(failure_attribution[key], f"failure_attribution.{key}")


def _requires_cleanup(execution_context: Dict[str, Any]) -> bool:
    run_mode = str(execution_context.get("run_mode", "")).strip()
    if run_mode and run_mode != "read-only":
        return True
    allowed_actions = set(_ensure_list(execution_context.get("allowed_actions")))
    return bool(allowed_actions & MUTATING_ACTIONS)


def validate_checkpoint(checkpoint: Dict[str, Any]) -> None:
    _require_map(checkpoint, "checkpoint")
    _require_fields(
        checkpoint,
        [
            "checkpoint_id",
            "schema_version",
            "stage",
            "name",
            "status",
            "risk_level",
            "source_baseline",
            "execution_context",
            "depends_on",
            "validate",
            "evidence",
            "governance",
            "promotion_gate",
            "staleness_policy",
        ],
        "checkpoint",
    )
    _require_non_empty_string(checkpoint["schema_version"], "schema_version")
    _require_non_empty_string(checkpoint["name"], "name")
    if checkpoint["status"] not in ALLOWED_STATUS:
        raise CheckpointValidationError(f"status must be one of {sorted(ALLOWED_STATUS)}")
    if checkpoint["risk_level"] not in ALLOWED_RISK_LEVELS:
        raise CheckpointValidationError(f"risk_level must be one of {sorted(ALLOWED_RISK_LEVELS)}")
    _validate_stage_and_id(checkpoint)
    _validate_source_baseline(_require_map(checkpoint["source_baseline"], "source_baseline"))
    _validate_execution_context(_require_map(checkpoint["execution_context"], "execution_context"))
    _validate_depends_on(checkpoint["depends_on"])
    _validate_steps(checkpoint.get("steps"))
    _validate_validate(_require_map(checkpoint["validate"], "validate"))
    _validate_evidence(_require_map(checkpoint["evidence"], "evidence"))
    _validate_governance(_require_map(checkpoint["governance"], "governance"))
    _validate_promotion_gate(_require_map(checkpoint["promotion_gate"], "promotion_gate"))
    _validate_staleness_policy(_require_map(checkpoint["staleness_policy"], "staleness_policy"))

    if _requires_cleanup(_require_map(checkpoint["execution_context"], "execution_context")):
        cleanup_policy = checkpoint.get("cleanup_policy")
        if cleanup_policy is None:
            raise CheckpointValidationError("cleanup_policy required for write checkpoints")
        _validate_cleanup_policy(_require_map(cleanup_policy, "cleanup_policy"))
        if cleanup_policy["required_for_write"] is not True:
            raise CheckpointValidationError("cleanup_policy.required_for_write must be true for write checkpoints")
    elif checkpoint.get("cleanup_policy") is not None:
        _validate_cleanup_policy(_require_map(checkpoint["cleanup_policy"], "cleanup_policy"))

    if checkpoint["status"] in {"failed", "degraded", "blocked"}:
        failure_attribution = checkpoint.get("failure_attribution")
        if failure_attribution is None:
            raise CheckpointValidationError("failure_attribution required for failed/degraded/blocked checkpoints")
        _validate_failure_attribution(_require_map(failure_attribution, "failure_attribution"))


def normalize_artifact_refs(refs: Any) -> List[Dict[str, Any]]:
    normalized = []
    for ref in _ensure_list(refs):
        item = _require_map(ref, "artifact_ref")
        stable = {}
        for key in ["type", "path", "packet_id", "report_id", "screenshot_path", "trace_path", "json_path", "ref_id"]:
            if key in item:
                stable[key] = item[key]
        if "path" not in stable and "screenshot_path" not in stable and "trace_path" not in stable and "json_path" not in stable:
            raise CheckpointValidationError("artifact refs must contain a stable path-like key")
        normalized.append(stable)
    return normalized


def build_rag_packet(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    validate_checkpoint(checkpoint)
    return {
        "packet_id": _stable_id("rag", checkpoint),
        "source_checkpoint_id": checkpoint["checkpoint_id"],
        "schema_version": checkpoint["schema_version"],
        "source_baseline": deepcopy(checkpoint["source_baseline"]),
        "execution_context": deepcopy(checkpoint["execution_context"]),
        "depends_on": deepcopy(checkpoint["depends_on"]),
        "validate": deepcopy(checkpoint["validate"]),
        "evidence": deepcopy(checkpoint["evidence"]),
        "governance": deepcopy(checkpoint["governance"]),
        "promotion_gate": deepcopy(checkpoint["promotion_gate"]),
        "staleness_policy": deepcopy(checkpoint["staleness_policy"]),
        "failure_attribution": deepcopy(checkpoint.get("failure_attribution")),
    }


SNAPSHOT_VERSION = "ui-test.checkpoint-execution.v1"


def capture_snapshot(definition, task, facts):
    if set(facts) != {"snapshot_id", "session_id", "captured_at", "run_id", "step_results"}:
        raise ValueError("incomplete current execution facts")
    snapshot = dict(deepcopy(facts), schema_version=SNAPSHOT_VERSION,
                    definition=deepcopy(definition), task=deepcopy(task))
    build_ui_test_packet(snapshot)
    return snapshot


def build_ui_test_packet(snapshot):
    from datetime import datetime
    if snapshot.get("schema_version") != SNAPSHOT_VERSION:
        raise ValueError("expected complete checkpoint execution snapshot")
    _require_fields(snapshot, ["definition", "task", "session_id", "captured_at", "run_id",
                               "snapshot_id", "step_results"], "execution snapshot")
    for key in ("session_id", "snapshot_id", "run_id"):
        _require_non_empty_string(snapshot[key], key)
    if datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("captured_at requires timezone")
    definition = snapshot["definition"]
    if set(definition) != {"definition_ref", "definition_version", "checkpoint_id", "applies_to", "steps"}:
        raise ValueError("invalid reusable definition")
    for key in ("definition_ref", "definition_version"):
        _require_non_empty_string(definition.get(key), key)
    packet = deepcopy(snapshot["task"])
    conditions = definition["applies_to"]
    scope = packet.get("scope", {})
    if not isinstance(conditions, dict) or not conditions or any(
        key not in scope or scope[key] != value for key, value in conditions.items()
    ):
        raise ValueError("definition applicability conflicts with current task scope")
    if definition["checkpoint_id"] != scope.get("checkpoint"):
        raise ValueError("definition conflicts with current checkpoint")
    if "steps" in packet:
        raise ValueError("supply reusable steps in the definition only")
    risks = {"R0": "r0-read-only", "R1": "r1-read-only-authenticated",
             "R2": "r2-ui-write-test", "R3": "r3-high-impact"}
    actions = {"open": "navigate", "inspect": "assert"}
    packet["steps"] = []
    for step in definition["steps"]:
        if set(step) != {"id", "name", "action", "risk", "required", "verification"}:
            raise ValueError("invalid definition step fields")
        if step["risk"] not in risks:
            raise ValueError("unknown definition step risk")
        _require_non_empty_string(step["verification"], "business assertion")
        packet["steps"].append({
            "step_id": step["id"], "action": actions.get(step["action"], step["action"]),
            "risk_level": risks[step["risk"]], "required": step["required"],
            "intent": step["name"], "postcondition": step["verification"],
        })
    import sys
    scripts = Path(__file__).resolve().parents[2] / "ui-test" / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from ui_test_core.packet_validator import validate_packet
    finally:
        sys.path.remove(str(scripts))
    source_id = packet.get("packet_id")
    if "packet_id" not in packet:
        packet["packet_id"] = _stable_id("checkpoint_packet", snapshot)
    errors = validate_packet(packet)
    if errors:
        raise ValueError(str(errors))
    if snapshot["run_id"] != packet["run"]["run_id"]:
        raise ValueError("step results belong to another run")
    results = snapshot["step_results"]
    if [r["step_id"] for r in results] != [s["step_id"] for s in packet["steps"]]:
        raise ValueError("incomplete or conflicting step results")
    for step, result in zip(packet["steps"], results):
        if set(result) != {"step_id", "status", "evidence_refs"}:
            raise ValueError("invalid execution step result")
        if result["status"] not in {"passed", "failed", "unknown", "skipped", "pending"}:
            raise ValueError("invalid step status")
        _require_string_list(result["evidence_refs"], "step evidence")
        step["evidence_refs"] = deepcopy(result["evidence_refs"])
        step["execution_status"] = result["status"]
        for ref in result["evidence_refs"]:
            if ref not in packet["artifact_refs"]:
                packet["artifact_refs"].append(ref)
    packet["lineage"]["source_refs"].extend([snapshot["snapshot_id"], definition["definition_ref"]])
    if source_id is not None:
        packet["lineage"]["parent_packet_id"] = source_id
        packet["lineage"]["source_refs"].append(source_id)
    packet["packet_id"] = _stable_id("checkpoint_packet", snapshot)
    return packet


def build_checkpoint_bundle(snapshot, review_notes=None):
    import sys
    scripts = Path(__file__).resolve().parents[2] / "ui-test-a2a-handoff" / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from a2a_handoff import pack
    finally:
        sys.path.remove(str(scripts))
    packet = build_ui_test_packet(snapshot)
    return dict(pack(packet, review_notes), ui_test_packet=packet,
                snapshot=deepcopy(snapshot), bundle_id=_stable_id("checkpoint_bundle", snapshot))


def load_json(path: Path) -> Dict[str, Any] | List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_validate(input_path: Path) -> None:
    payload = load_json(input_path)
    checkpoints = payload if isinstance(payload, list) else [payload]
    for checkpoint in checkpoints:
        validate_checkpoint(checkpoint)


def _run_bundle(input_path: Path, output_path: Path) -> None:
    payload = load_json(input_path)
    checkpoints = payload if isinstance(payload, list) else [payload]
    bundles = [build_checkpoint_bundle(checkpoint) for checkpoint in checkpoints]
    save_json(output_path, bundles if isinstance(payload, list) else bundles[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Checkpoint schema validator and bundle builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate checkpoint JSON")
    validate_parser.add_argument("--input", type=Path, required=True)

    bundle_parser = subparsers.add_parser("bundle", help="build downstream checkpoint bundle")
    bundle_parser.add_argument("--input", type=Path, required=True)
    bundle_parser.add_argument("--output", type=Path, required=True)

    capture = subparsers.add_parser("capture", help="capture current task and execution facts")
    for field in ("definition", "task", "facts", "output"):
        capture.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()

    if args.command == "capture":
        save_json(args.output, capture_snapshot(load_json(args.definition), load_json(args.task), load_json(args.facts)))
    elif args.command == "validate":
        _run_validate(args.input)
    elif args.command == "bundle":
        _run_bundle(args.input, args.output)


if __name__ == "__main__":
    main()
