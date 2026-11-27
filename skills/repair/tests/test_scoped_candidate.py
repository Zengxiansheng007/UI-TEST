"""Offline V5 transactions for the actual repair CLI; no business attempt is run by the Skill."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

from ui_test_core.asset_revision import AssetCatalog, digest
from ui_test_core.case_contracts import canonical_hash
from ui_test_core.finalization_transaction import FinalizationTransaction


ROOT = Path(__file__).resolve().parents[3]
MAIN = ROOT / "skills/ui-test"
TEMPLATE = ROOT / "examples/todomvc-repair"


def save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf8")


def transaction(project, run, scope, row, *, cause=None, write_state="not_attempted"):
    original = runpy.run_path(str(MAIN / "tests/test_finalization_transaction.py"))
    result, index = original["_candidate"]()
    status = "failed" if cause else "passed"
    case = scope["case_id"]
    use = dict(run_id=run, scope=scope, case_id=case, step_id=scope["step_id"], asset_id="locator.target",
               version=row["version"], sha256=row["sha256"], entered=True, attempt_ref=result["attempt_ref"],
               action_result=status, assertion_result=status, source_hash=digest((project/"source_case.py").read_bytes()))
    if cause:
        use["failure"] = dict(cause=cause)
    attempt = project / "runs" / run
    save(attempt / "use.json", use)
    result.update(run_id=run, case_id=case, overall_status=status, write_state=write_state,
                  submit_count=int(write_state != "not_attempted"), evidence_refs=["use.json"],
                  step_results=[dict(step_id=use["step_id"], status=status, evidence_refs=["use.json"],
                                     asset_use_hash=canonical_hash(use))])
    result["pytest_phase_status"]["call"] = status
    del result["run_result_hash"]
    result["run_result_hash"] = canonical_hash(result)
    index.update(case_id=case, run_id=run, run_result_hash=result["run_result_hash"], evidence_refs=["use.json"])
    FinalizationTransaction(attempt).commit(transaction_id=result["transaction_id"], run_id=run,
                                            node_id=result["node_id"], run_result=result, evidence_index=index)


def command(directory, name, request, *, fail=False):
    path = directory / (name + ".json")
    save(path, request)
    completed = subprocess.run([sys.executable, "-B", MAIN/"scripts/ui_test_suite.py", "repair", "--input", path],
                               cwd=directory, capture_output=True, text=True,
                               env=dict(os.environ, UI_TEST_SUITE=str(MAIN)))
    if fail:
        assert completed.returncode != 0
        return completed.stderr
    assert completed.returncode == 0, completed.stderr
    answer = json.loads(completed.stdout)
    save(directory / (name + "-answer.json"), answer)
    return answer


def test_scoped_candidate_and_v5_proof(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(TEMPLATE))
    monkeypatch.syspath_prepend(str(MAIN))
    sample = runpy.run_path(str(TEMPLATE/"prepare.py"))
    project, trial = tmp_path/"project", tmp_path/"trial"
    sample["initialize"](project)
    key, scope = sample["KEY"], sample["SCOPE"]
    catalog = AssetCatalog(project)
    _, original = catalog.pin()
    row = original[key]
    source = project / "proposal.py"
    shutil.copyfile(TEMPLATE/"repairs/project-source/target.py", source)
    case = scope["case_id"]
    request = dict(project=str(project), scope=scope, authorization=dict(approved=True, scope=scope),
                   asset_id=key, failure_run="FAIL1", source_cases={case:dict(source="source_case.py",
                   bindings=["script.complete"])}, candidate_source=source.name)
    transaction(project, "FAIL1", scope, row, cause="asset")
    candidate = command(tmp_path, "candidate", request)
    assert candidate["status"] == "candidate" and candidate["pending_cases"] == [case]
    assert candidate["impact"]["direct"] == ["component.ready"]
    assert candidate["impact"]["transitive"] == ["script.complete"]
    assert candidate["original"]["version"] == 1 and candidate["candidate"]["version"] == 2
    shutil.copytree(project, trial)
    raw = source.read_bytes()
    tested = dict(row, version=2, sha256=digest(raw))
    trial_catalog = AssetCatalog(trial)
    trial_catalog.publish(key, tested, raw, expected_revision=0)
    transaction(trial, "QUAL1", scope, tested, write_state="write_succeeded_verified")
    verified = command(tmp_path, "verified", dict(request, proof_project=str(trial), proof_runs={case:"QUAL1"}))
    assert verified["status"] == "verified-candidate"
    assert verified["verification"][case]["run_id"] == "QUAL1" and not verified["pending_cases"]
    assert not verified["activation_performed"]
    saved = (project/"source_case.py").read_bytes()
    (project/"source_case.py").write_bytes(saved + b"# changed goal")
    assert command(tmp_path, "changed", request)["reason"] == "original_assertion_changed"
    (project/"source_case.py").write_bytes(saved)
    for cause, state in (("environment", "not_attempted"), ("data", "not_attempted"),
                         ("unknown", "not_attempted"), ("asset", "write_outcome_unknown")):
        run = "CASE" + cause
        transaction(project, run, scope, row, cause=cause, write_state=state)
        stopped = command(tmp_path, run, dict(request, failure_run=run))
        assert stopped["stop_dependents"] and stopped["business_attempts_added"] == 0
        assert stopped["reason"] == ("write_outcome_unknown" if state == "write_outcome_unknown"
                                      else "asset_cause_unconfirmed")
        assert not stopped["activation_performed"] and "candidate" not in stopped
    wrong_scope = dict(scope, environment="staging")
    denied = dict(request, scope=wrong_scope, authorization=dict(approved=True, scope=wrong_scope))
    assert "failure scope differs" in command(tmp_path, "cross-env", denied, fail=True)
    assert catalog.revision() == 0 and not catalog.paused(key, 1, scope)
    assert catalog.pin()[1][key]["sha256"] == row["sha256"]
    assert (project/"source_case.py").read_bytes() == saved
    assert {"project", "scope", "failure_run", "asset_id"} <= set(command(tmp_path, "missing", {})["missing"])
