"""Project hooks for the standard attempt store and RunResultV5 finalization transaction."""
import json
from datetime import datetime, timezone
from pathlib import Path

from ui_test_core.asset_revision import encoded, replace
from ui_test_core.case_contracts import canonical_hash
from ui_test_core.run_evidence_linker import build_evidence_index_v2, build_run_result_v5
from ui_test_core.stage_write_budget import StagePermitLedger
from source_case import TARGET, OTHER

ROOT = Path(__file__).resolve().parent


def begin(context, out):
    assert context.approved and context.environment == "test" and context.risk_level == "r2-ui-write-test"
    budget = context.config_summary["stage_write_budget"]
    assert budget["phase_ids"] == ["add-other", "add-target", "check-target"]
    approval = dict(schema_version="ui-test.r2-approval-record.v3", approval_id="APPROVAL-"+context.run_id,
                    approval_source=context.approval_source, run_id=context.run_id, node_id=context.node_id,
                    case_id=context.case_id, branch_id=context.branch_id, environment=context.environment,
                    allowed_action="public-todomvc-visible-ui", channel="visible-ui", max_submit_count=3,
                    decision="approved", credential_values_persisted=False, reusable_across_runs=False,
                    risk_level=context.risk_level, runner_digest=context.runner_digest, stage_write_budget=budget)
    boundary = ("run_id","case_id","environment","allowed_action","channel","max_submit_count")
    approval["boundary_hash"] = canonical_hash({k:approval[k] for k in boundary})
    replace(out/"approval.json", encoded(approval))
    params = [dict(parameter_id=k, ref="source:"+k, source_type="value", value=v)
              for k,v in (("target",TARGET),("other",OTHER))]
    snapshot = dict(schema_version="ui-test.resolved-test-data.v2", run_id=context.run_id, case_id=context.case_id,
                    branch_id=context.branch_id, build_fingerprint=context.runner_digest, test_data_hash=canonical_hash(params),
                    parameter_manifest_hash=canonical_hash(params), parameters=params, stage_write_budget=budget,
                    sealed_at=datetime.now(timezone.utc).isoformat())
    snapshot["snapshot_hash"] = canonical_hash(snapshot)
    replace(out/"resolved-test-data.json", encoded(snapshot))
    return StagePermitLedger(budget)


def pytest_ui_test_project_config_path():
    return str(ROOT/"ui-test.project.yaml")


def pytest_ui_test_execution_evidence_root():
    return str(ROOT/"execution-evidence")


def pytest_ui_test_finalization_target_v1(run_id, node_id, attempt_store):
    return {"run_root":str(ROOT/"runs"/run_id)}


def pytest_ui_test_build_finalization_candidate_v1(run_id,node_id,transaction_id,pre_terminal_events_hash,
                                                  pytest_phase_status,attempt_store):
    c = attempt_store.read_execution_context(run_id=run_id,node_id=node_id)
    ref, sha = attempt_store.read_execution_context_ref_and_hash(run_id=run_id,node_id=node_id)
    out = ROOT/"runs"/run_id
    use = json.loads((out/"use.json").read_bytes())
    assert (run_id,c["attempt_ref"],c["case_id"]) == (use["run_id"],use["attempt_ref"],use["case_id"])
    phases = use["phase_results"]
    n = sum(p["submit_count"] for p in phases)
    state = next((p["write_state"] for p in phases if p["submit_count"] and p["write_state"]!="write_succeeded_verified"),
                 "write_succeeded_verified" if n else "not_attempted")
    passed = all(s=="passed" for s in pytest_phase_status.values())
    if passed:
        assert use["assertion_result"] == use["action_result"] == "passed"
    refs = ["use.json",*[p.name for p in sorted(out.glob("*.png"))]]
    step = dict(step_id="COMPLETE",status="passed" if passed else "failed",evidence_refs=refs,
                asset_use_hash=canonical_hash(use))
    result = build_run_result_v5(run_root=out,snapshot_path=out/"resolved-test-data.json",
        transaction_id=transaction_id,session_id=c["session_id"],execution_context_ref=ref,execution_context_hash=sha,
        attempt_ref=c["attempt_ref"],pre_terminal_events_hash=pre_terminal_events_hash,approval_ref="approval.json",
        approval_hash=canonical_hash(json.loads((out/"approval.json").read_bytes())),run_id=run_id,node_id=node_id,
        case_id=c["case_id"],branch_id=c["branch_id"],pytest_phase_status=dict(pytest_phase_status),
        overall_status="passed" if passed else "failed",write_state=state,submit_count=n,step_results=[step],
        evidence_refs=refs,stage_write_budget=c["config_summary"]["stage_write_budget"],phase_results=phases)
    return dict(run_result=result,evidence_index=build_evidence_index_v2(result,run_result_ref="objects/"+"0"*64+".json"))
