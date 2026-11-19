import json
import os
from pathlib import Path

from scripts.ui_test_core.case_contracts import canonical_hash
from scripts.ui_test_core.run_evidence_linker import build_evidence_index_v2, build_run_result_v5

pytest_plugins = ("scripts.ui_test_core.pytest_runtime_plugin",)
ROOT = Path(os.environ["CONTROLLED_UI_EVIDENCE"])


def pytest_ui_test_project_config_path():
    return str(Path(__file__).with_name("project.json"))


def pytest_ui_test_execution_evidence_root():
    return str(ROOT)


def pytest_ui_test_finalization_target_v1(run_id, node_id, attempt_store):
    return {"run_root": str(ROOT / "runs" / run_id)}


def pytest_ui_test_build_finalization_candidate_v1(
    run_id, node_id, transaction_id, pre_terminal_events_hash, pytest_phase_status, attempt_store
):
    root = ROOT / "runs" / run_id
    context = attempt_store.read_execution_context(run_id=run_id, node_id=node_id)
    reference, digest = attempt_store.read_execution_context_ref_and_hash(run_id=run_id, node_id=node_id)
    outcome = json.loads((root / "observed.json").read_text())
    approval = json.loads((root / "approval.json").read_text())
    result = build_run_result_v5(
        run_root=root, snapshot_path=root / "snapshot.json", transaction_id=transaction_id,
        session_id=context["session_id"], execution_context_ref=reference, execution_context_hash=digest,
        attempt_ref=context["attempt_ref"], pre_terminal_events_hash=pre_terminal_events_hash,
        approval_ref="approval.json", approval_hash=canonical_hash(approval), run_id=run_id,
        node_id=node_id, case_id=context["case_id"], branch_id=context["branch_id"],
        pytest_phase_status=dict(pytest_phase_status),
        overall_status="passed" if all(value == "passed" for value in pytest_phase_status.values())
        and outcome["write_state"] == "write_succeeded_verified" else "failed",
        stage_write_budget=context["config_summary"].get("stage_write_budget"),
        phase_results=outcome.get("phase_results"),
        write_state=outcome["write_state"], submit_count=outcome["submit_count"],
    )
    return {"run_result": result, "evidence_index": build_evidence_index_v2(result, run_result_ref="objects/pending.json")}
