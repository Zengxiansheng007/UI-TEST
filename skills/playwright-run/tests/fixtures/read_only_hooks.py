"""Controlled finalization candidates for a local read-only assertion."""
import pathlib

import json
from scripts.ui_test_core.case_contracts import canonical_hash
from scripts.ui_test_core.run_evidence_linker import build_run_result_v5, build_evidence_index_v2
def pytest_ui_test_project_config_path():
    return str(pathlib.Path(__file__).with_name("ui-test.project.yaml"))

def pytest_ui_test_finalization_target_v1(run_id, node_id, attempt_store):
    return {"run_root": str(pathlib.Path.cwd() / "runs" / run_id)}

def pytest_ui_test_build_finalization_candidate_v1(run_id, node_id, transaction_id, pre_terminal_events_hash, pytest_phase_status, attempt_store):
    from scripts.ui_test_core.run_evidence_linker import build_read_only_boundary
    ctx = attempt_store.read_execution_context(run_id=run_id, node_id=node_id)
    ref, digest = attempt_store.read_execution_context_ref_and_hash(run_id=run_id, node_id=node_id)
    root = pathlib.Path("runs") / run_id
    boundary = build_read_only_boundary(ctx)
    if "forged-boundary" in node_id:
        boundary["max_submit_count"] = 1
    (root / "boundary.json").write_text(json.dumps(boundary))
    status = "passed" if all(v == "passed" for v in pytest_phase_status.values()) else "failed"
    result = build_run_result_v5(
        run_root=root, snapshot_path=root / "reports/resolved-test-data.json", run_id=run_id,
        node_id=node_id, case_id=ctx["case_id"], branch_id=ctx["branch_id"], session_id=ctx["session_id"],
        transaction_id=transaction_id, execution_context_ref=ref, execution_context_hash=digest,
        attempt_ref=ctx["attempt_ref"], pre_terminal_events_hash=pre_terminal_events_hash,
        approval_ref="boundary.json", approval_hash=canonical_hash(boundary), risk_level=ctx["risk_level"],
        overall_status=status, pytest_phase_status=pytest_phase_status, write_state="not_attempted",
        submit_count=0, step_results=[{"step_id": "inspect-row", "status": status}])
    return {"run_result": result, "evidence_index": build_evidence_index_v2(result, run_result_ref="objects/pending.json")}
