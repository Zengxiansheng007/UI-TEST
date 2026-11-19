import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent / "ui-test" / "scripts"))
from ui_test_core.run_evidence_linker import canonical_hash
from ui_test_core.path_utils import io_path


@pytest.mark.parametrize("mode", ["passed", "failed", "v2", "unknown", "hash", "missing", "identity", "invalid-pass", "missing-snapshot"])
def test_report_cli(tmp_path, mode):
    data = json.loads((PACKAGE / "assets/sample-run.json").read_text(encoding="utf8"))
    result = data["run_result"]
    data["run_root"] = str(PACKAGE / "assets/sample-run-root")
    if mode == "missing-snapshot":
        data["run_root"] = str(tmp_path)
    if mode == "failed":
        result["overall_status"] = "failed"
        result["pytest_phase_status"]["call"] = "failed"
    if mode in ["v2", "unknown"]:
        result["schema_version"] = "ui-test.run-result." + mode
    if mode == "identity":
        data["report"]["session_id"] = "different"
    if mode == "missing":
        del result["write_state"]
    if mode == "invalid-pass":
        result["submit_count"] = 0
    result["run_result_hash"] = canonical_hash({k: v for k, v in result.items() if k != "run_result_hash"})
    if mode == "hash":
        result["submit_count"] = 0
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data), encoding="utf8")
    output = tmp_path / "output"
    run = subprocess.run([sys.executable, str(PACKAGE / "scripts/generate_report.py"), "--input", str(source), "--output-root", str(output)], capture_output=True)
    if mode in ["passed", "failed"]:
        assert run.returncode == 0, run.stderr
        summary = json.loads(next(io_path(output).rglob("execution-summary.json")).read_text(encoding="utf8"))
        assert summary["status"] == mode
        assert summary["external_acceptance"] == summary["artifact_commit"] == "not_provided"
        assert json.loads(next(io_path(output).rglob("run-result.json")).read_text(encoding="utf8")) == result
    else:
        assert run.returncode and not output.exists()

@pytest.mark.parametrize("mode", ["committed", "tampered", "incomplete-chain"])
def test_report_reads_finalization_files(tmp_path, mode):
    import shutil
    from ui_test_core.finalization_transaction import commit_finalization
    from ui_test_core.run_evidence_linker import build_evidence_index_v2
    data = json.loads((PACKAGE / "assets/sample-run.json").read_text(encoding="utf8"))
    result = data["run_result"]
    root = tmp_path / "r"
    shutil.copytree(PACKAGE / "assets/sample-run-root", root)
    data["run_root"] = "r"
    evidence = build_evidence_index_v2(result, run_result_ref="finalization/objects/run-result.json")
    commit_finalization(run_root=root, transaction_id=result["transaction_id"], run_id=result["run_id"],
                        node_id=result["node_id"], run_result=result, evidence_index=evidence)
    if mode == "tampered":
        path = root / "finalization/finalization-receipt.json"
        receipt = json.loads(path.read_text(encoding="utf8"))
        receipt["run_id"] = "another-run"
        path.write_text(json.dumps(receipt), encoding="utf8")
    if mode == "incomplete-chain":
        data["external_acceptance_refs"] = {}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data), encoding="utf8")
    output = tmp_path / "out"
    run = subprocess.run([sys.executable, str(PACKAGE / "scripts/generate_report.py"), "--input", str(source),
                          "--output-root", str(output)], capture_output=True)
    if mode == "committed":
        assert run.returncode == 0, run.stderr
        summary = json.loads(next(io_path(output).rglob("execution-summary.json")).read_text(encoding="utf8"))
        assert summary["artifact_commit"] == "committed"
        assert summary["external_acceptance"] == "not_provided"
    else:
        assert run.returncode and not output.exists()

@pytest.mark.parametrize("tamper", [False, True])
def test_external_record_from_files(tmp_path, tamper):
    from ui_test_core.finalization_transaction import commit_finalization
    from ui_test_core.pycharm_acceptance import _build_pycharm_acceptance_result
    from ui_test_core.run_evidence_linker import build_evidence_index_v2
    sys.path.insert(0, str(PACKAGE.parent / "ui-test" / "tests"))
    sys.path.insert(0, str(PACKAGE.parent / "ui-test"))
    from test_st013_pycharm_acceptance import _documents

    data = json.loads((PACKAGE / "assets/sample-run.json").read_text(encoding="utf8"))
    documents = _documents(helper_path_hash="sha256:" + "1" * 64, helper_content_hash="sha256:" + "2" * 64)
    context, approval, result = (documents[key] for key in ("context", "approval", "run"))
    snapshot_ref = result["resolved_test_data_ref"]
    snapshot = json.loads((PACKAGE / "assets/sample-run-root" / snapshot_ref).read_text(encoding="utf8"))
    snapshot.update(run_id=result["run_id"], case_id=result["case_id"])
    del snapshot["snapshot_hash"]
    snapshot["snapshot_hash"] = canonical_hash(snapshot)
    (tmp_path / snapshot_ref).parent.mkdir(parents=True)
    (tmp_path / snapshot_ref).write_text(json.dumps(snapshot), encoding="utf8")
    result.update(resolved_test_data_hash=snapshot["snapshot_hash"], approval_hash=canonical_hash(approval),
                  execution_context_hash=canonical_hash(context))
    del result["run_result_hash"]
    result["run_result_hash"] = canonical_hash(result)
    transaction = commit_finalization(run_root=tmp_path, transaction_id=result["transaction_id"], run_id=result["run_id"],
                                     node_id=result["node_id"], run_result=result, evidence_index=build_evidence_index_v2(
                                         result, run_result_ref="finalization/objects/run-result.json"))
    commit, receipt = transaction["manifest"], transaction["receipt"]
    terminal, session = documents["terminal"], documents["session"]
    terminal.update(commit_manifest_hash=canonical_hash(commit), receipt_hash=canonical_hash(receipt))
    session["nodes"][0].update(terminal_hash=canonical_hash(terminal), receipt_hash=canonical_hash(receipt))
    del session["session_result_hash"]
    session["session_result_hash"] = canonical_hash(session)
    records = dict(pytest_session_result=session, approval_record=approval, execution_context=context,
                   terminal=terminal, process_evidence=documents["process"])
    records["acceptance_result"] = _build_pycharm_acceptance_result(
        run_result=result, finalization_commit=commit, finalization_receipt=receipt, **records,
        authorization_ref=result["approval_ref"], process_evidence_ref="console/process.json",
        finalization_commit_ref=terminal["commit_manifest_ref"], finalization_receipt_ref=terminal["receipt_ref"],
        pytest_session_result_ref="sessions/session.json", evaluation_authority="independent-qa")
    if tamper:
        records["process_evidence"]["observed_process_exit_code"] = 1
    data.update(run_root=".", run_result=result, external_acceptance_refs={k: k + ".json" for k in records})
    for key in ("node_id", "case_id", "run_id", "transaction_id", "session_id"):
        data["report"][key] = result[key]
    for key, value in records.items():
        (tmp_path / data["external_acceptance_refs"][key]).write_text(json.dumps(value), encoding="utf8")
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data), encoding="utf8")
    output = tmp_path / "out"
    run = subprocess.run([sys.executable, str(PACKAGE / "scripts/generate_report.py"), "--input", str(source),
                          "--output-root", str(output)], capture_output=True)
    if tamper:
        assert run.returncode and not output.exists()
    else:
        assert run.returncode == 0, run.stderr
        summary = json.loads(next(io_path(output).rglob("execution-summary.json")).read_text(encoding="utf8"))
        assert summary["external_acceptance"] == "passed"
        assert summary["evaluation_authority"] == "independent-qa"
