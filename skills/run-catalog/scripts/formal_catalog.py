"""Project catalog milestones at actual pytest collection, admission and terminal publication."""
import sys
from pathlib import Path

from ui_test_core.artifact_layout import ProjectLayout, batch_stage_id
from .stage_events import record_attempt, stage_started


def selected_cases(items):
    result = []
    for item in items:
        if item.get_closest_marker("ui_test"):
            owner = {}
            for name in ("case_id", "branch_id"):
                marker = item.get_closest_marker(name)
                owner[name] = marker.args[0] if marker and marker.args and isinstance(marker.args[0], str) else item.nodeid
            result.append(owner)
    return result


def registration_notice(error):
    if error:
        print("UI-Test catalog refresh pending: " + error, file=sys.stderr)


def begin_batch(task_ref, batch_ref, manifest, started_at):
    root = manifest.get("evidence_root")
    project = ProjectLayout.from_evidence(Path(root) / "sessions") if root else None
    if project and manifest.get("owners"):
        registration_notice(stage_started(project.root, "playwright", batch_stage_id(task_ref, batch_ref),
                                          started_at, manifest["owners"]))


def recover_terminal(root, case_id, branch_id, attempt):
    """Read a terminal sealed before a producer could replace its running event."""
    from ui_test_core.case_contracts import canonical_hash
    from ui_test_core.codex_dispatch_state import read
    from ui_test_core.path_planner import validate_existing_path_containment
    from .run_catalog import checked_ref
    from ui_test_core.session_evidence import verify_node_evidence
    source = root / checked_ref(root, attempt["execution_ref"])
    terminal = source.with_name("terminal.json")
    validate_existing_path_containment(root, terminal)
    start = source.with_name("attempt-start.json")
    validate_existing_path_containment(root, start)
    if source.name != "execution-context.json" or not all(path.is_file() for path in (source, terminal, start)):
        return attempt
    ctx, result = read(source), read(terminal)
    if (ctx["case_id"], ctx["branch_id"], ctx["attempt_ref"]) != (case_id, branch_id, attempt["attempt_ref"]):
        return attempt
    finalization = read(start)["finalization_mode"]
    receipt = result.get("receipt_ref")
    if receipt:
        finalization = "committed" if receipt.startswith("runs/") else "failed"
    elif finalization == "transaction-v1":
        finalization = "missing"
    node = dict(run_id=ctx["run_id"], node_id=ctx["node_id"], attempt_ref=ctx["attempt_ref"],
                terminal_ref=ctx["attempt_ref"] + "/terminal.json", terminal_hash=canonical_hash(result),
                receipt_ref=receipt, receipt_hash=result.get("receipt_hash"), finalization_status=finalization)
    evidence = source.parents[2]
    if not verify_node_evidence(evidence, ctx["session_id"], node):
        return attempt
    source_ref = terminal.relative_to(root).as_posix()
    if finalization == "committed":
        from ui_test_core.execution_attempt_store import ExecutionAttemptStore
        from ui_test_core.finalization_transaction import FinalizationTransaction
        target = ExecutionAttemptStore(evidence_root=evidence).session_run_target(run_id=ctx["run_id"], node_id=ctx["node_id"])
        closure = FinalizationTransaction(target).read_committed(immutable_snapshot=True)
        final = Path(target) / "finalization"
        return dict(attempt, status=closure["run_result"]["overall_status"],
                    execution_ref=(final / closure["manifest"]["run_result_ref"]).relative_to(root).as_posix(),
                    evidence_ref=(final / closure["manifest"]["evidence_index_ref"]).relative_to(root).as_posix())
    return dict(attempt, status=result["status"], execution_ref=source_ref, evidence_ref=source_ref)


def attempt_checkpoint(stage, evidence_root, context, store, status, run_root=None):
    project = ProjectLayout.from_evidence(Path(evidence_root) / "sessions")
    if project is None:
        return
    owner = dict(case_id=context.case_id, branch_id=context.branch_id)
    source = Path(evidence_root) / context.attempt_ref / ("execution-context.json" if status == "running" else "terminal.json")
    index = None
    if run_root:
        from ui_test_core.finalization_transaction import FinalizationTransaction
        closure = FinalizationTransaction(run_root).read_committed(immutable_snapshot=True)
        if closure:
            final = Path(run_root) / "finalization"
            source = final / closure["manifest"]["run_result_ref"]
            index = final / closure["manifest"]["evidence_index_ref"]
            status = closure["run_result"]["overall_status"]
    attempt = dict(attempt_ref=context.attempt_ref, status=status, execution_ref=source.resolve().relative_to(project.root).as_posix(),
                   evidence_ref=index.resolve().relative_to(project.root).as_posix() if index else None)
    saved = store.read_execution_context(run_id=context.run_id, node_id=context.node_id)
    if saved and saved.get("binding"):
        attempt.update(version=saved["binding"].get("version"), binding=saved["binding"])
    registration_notice(record_attempt(project.root, "playwright", stage, owner, attempt))
