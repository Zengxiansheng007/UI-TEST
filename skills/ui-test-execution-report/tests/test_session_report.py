import json
import subprocess
import sys
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent / "ui-test/scripts"))
from ui_test_core.case_contracts import canonical_hash, validate_document


def report(evidence_root, output, *extra, exit_code=0, session_file=None):
    args = [sys.executable, str(PACKAGE / "scripts/generate_report.py"),
            "--session-result", str(session_file or evidence_root / "sessions/session-a.json"),
            "--evidence-root", str(evidence_root), "--output-root", str(output), *extra]
    if exit_code is not None:
        args.extend(["--observed-exit-code", str(exit_code)])
    run = subprocess.run(args, capture_output=True, encoding="utf8")
    assert run.returncode == 0, run.stderr
    artifacts = json.loads(run.stdout)
    return (json.loads(Path(artifacts["execution_summary"]).read_text(encoding="utf8")),
            Path(artifacts["report_html"]).read_text(encoding="utf8"))


def test_hard_exit_without_session_is_reported(tmp_path):
    summary, html = report(tmp_path, tmp_path / "review", exit_code=27)
    assert summary["status"] == "incomplete"
    assert summary["observed_exit_code"] == 27 and summary["pytest_exitstatus"] is None
    assert "session-result-missing" in summary["issues"]
    assert "session-result-missing" in html


def save_session(root, document):
    document.pop("session_result_hash", None)
    document["session_result_hash"] = canonical_hash(document)
    path = root / "sessions/session-a.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf8")
    return path


def lost_worker():
    return {"schema_version": "ui-test.pytest-session-result.v2", "session_id": "session-a",
            "execution_origin": "cli", "origin_evidence_digest": "sha256:" + "0" * 64,
            "batch_id": "batch-ab", "expected_nodes": ["test_ab.py::test_a", "test_ab.py::test_b"],
            "nodes": [{"node_id": "test_ab.py::test_a", "disposition": "unknown",
                       "finalization_status": "missing", "missing_reason": "worker-lost"}],
            "worker_errors": ["gw1 crashed"], "collection_consistent": False, "pytest_exitstatus": 1,
            "all_required_nodes_committed": False, "session_status": "failed", "recorded_at": "2026-11-20T00:00:00Z"}


def test_worker_loss_preserves_recorded_node_and_names_missing_node(tmp_path):
    session = lost_worker()
    path = save_session(tmp_path, session)
    original = path.read_bytes()
    summary, html = report(tmp_path, tmp_path / "review", "--expected-batch-id", "batch-ab", exit_code=1)
    assert summary["status"] == "incomplete"
    assert summary["batch_id"] == "batch-ab" and summary["expected_nodes"] == session["expected_nodes"]
    assert summary["worker_errors"] == ["gw1 crashed"] and summary["collection_consistent"] is False
    assert summary["nodes"][0]["missing_reason"] == "worker-lost"
    assert summary["missing_nodes"] == ["test_ab.py::test_b"]
    assert summary["pytest_exitstatus"] == summary["observed_exit_code"] == 1
    assert "gw1 crashed" in html and "test_ab.py::test_b" in html
    assert path.read_bytes() == original


@pytest.mark.parametrize(("mutation", "code"), [
    ("extra-row", "node-set-mismatch"), ("conflict", "duplicate-node"),
    ("different-batch", "batch-id-mismatch"), ("wrong-exit", "exit-code-mismatch"),
    ("no-exit", "observed-exit-missing"), ("no-collection", "collection-unconfirmed"),
    ("no-workers", "worker-errors-unreported"), ("bad-hash", "session-hash-mismatch"),
    ("no-terminal", "node-evidence-invalid")])
def test_conflicts_are_visible_even_when_source_claims_pass(tmp_path, mutation, code):
    session = lost_worker()
    node = {"node_id": session["expected_nodes"][0], "disposition": "passed", "finalization_status": "committed",
            "run_id": "run-a", "terminal_ref": "attempts/a/terminal.json", "terminal_hash": "sha256:" + "1" * 64,
            "receipt_ref": "runs/run-a/finalization/receipt.json", "receipt_hash": "sha256:" + "2" * 64}
    session.update(expected_nodes=[node["node_id"]], nodes=[node], session_status="passed", all_required_nodes_committed=True,
                   pytest_exitstatus=0, worker_errors=[], collection_consistent=True)
    if mutation == "extra-row":
        session["nodes"].append(dict(node, node_id="other.py::test"))
    if mutation == "conflict":
        session["nodes"].append(dict(node, run_id="run-b"))
    if mutation == "no-collection":
        del session["collection_consistent"]
    if mutation == "no-workers":
        del session["worker_errors"]
    path = save_session(tmp_path, session)
    if mutation == "bad-hash":
        path.write_text(path.read_text(encoding="utf8").replace("run-a", "run-c"), encoding="utf8")
    expected = "other" if mutation == "different-batch" else "batch-ab"
    exit_code = {"no-exit": None, "wrong-exit": 2}.get(mutation, 0)
    summary, _ = report(tmp_path, tmp_path / "review", "--expected-batch-id", expected, exit_code=exit_code)
    assert summary["status"] == "incomplete"
    assert code in summary["issues"]


@pytest.mark.parametrize("duplicate", [False, True], ids=["ordinary", "duplicate"])
def test_real_pytest_exit_and_terminal_files_control_batch_pass(tmp_path, duplicate):
    producer = PACKAGE.parent / "ui-test"
    evidence = tmp_path / "evidence"
    config = producer / "assets/fixtures/specified-runner/project.json"
    (tmp_path / "conftest.py").write_text(
        f"import sys\nsys.path.insert(0, {str(producer)!r})\n"
        "pytest_plugins = ['scripts.ui_test_core.pytest_runtime_plugin']\n"
        f"def pytest_ui_test_execution_evidence_root(): return {str(evidence)!r}\n"
        f"def pytest_ui_test_project_config_path(): return {str(config)!r}\n", encoding="utf8")
    (tmp_path / "test_batch.py").write_text(
        "import pytest\npytestmark = [pytest.mark.ui_test, pytest.mark.r0, pytest.mark.case_id('C'), pytest.mark.branch_id('B')]\n"
        "@pytest.mark.parametrize('value', [1, 2])\ndef test_value(value, ui_test_execution_context):\n"
        "    assert ui_test_execution_context.node_id.endswith(f'[{value}]')\n", encoding="utf8")
    workers = []
    if duplicate:
        pytest.importorskip("xdist")
        workers = ["-n", "2", "--dist=each"]
    child = subprocess.run([sys.executable, "-m", "pytest", "-q", *workers, "test_batch.py", "--ui-batch-id", "batch-ab"],
                           cwd=tmp_path, capture_output=True)
    assert child.returncode == int(duplicate), child.stdout
    source, = (evidence / "sessions").glob("*.json")
    summary, html = report(evidence, tmp_path / "out", "--expected-batch-id", "batch-ab",
                        exit_code=child.returncode, session_file=source)
    assert len(summary["nodes"]) == 2
    if duplicate:
        denied = ["test_batch.py::test_value[1]", "test_batch.py::test_value[2]"]
        assert summary["denied_duplicate_nodes"] == denied
        assert summary["status"] == "failed" and all(n["evidence_verified"] for n in summary["nodes"])
        assert all(n["disposition"] == "passed" for n in summary["nodes"])
        assert all(f"<li>{node}</li>" in html for node in denied) and "重复投递已拒绝" in html
        doc = json.loads(source.read_text(encoding="utf-8"))
        doc.update(session_status="passed", pytest_exitstatus=0)
        issues = validate_document(doc, "pytest-session-result-v2.schema.json")
        assert "E_SESSION_INCONSISTENT_PASS" in {issue["code"] for issue in issues}
        doc["session_result_hash"] = canonical_hash({k: v for k, v in doc.items() if k != "session_result_hash"})
        source.write_text(json.dumps(doc), encoding="utf-8")  # 仅修改临时测试证据。
        inconsistent, _ = report(evidence, tmp_path / "contradiction", exit_code=0, session_file=source)
        assert inconsistent["status"] == "incomplete"
        assert "duplicate-dispatch-in-passed-session" in inconsistent["issues"]
        return
    assert summary["status"] == "passed"
    assert "Playwright 正式执行报告" in html and 'aria-label="用例与关键节点"' in html
    assert all(n["evidence_verified"] for n in summary["nodes"])
    assert summary["external_acceptance"] == "not_provided"
    doc = json.loads(source.read_text(encoding="utf8"))
    extra = "test_extra.py::test_unselected"
    doc["unexpected_nodes"] = [extra]
    doc.pop("session_result_hash")
    doc["session_result_hash"] = canonical_hash(doc)
    original = source.read_bytes()
    source.write_text(json.dumps(doc), encoding="utf8")
    inconsistent, rendered = report(evidence, tmp_path / "extra", session_file=source)
    assert inconsistent["status"] == "incomplete"
    assert inconsistent["unexpected_nodes"] == [extra] and extra in rendered
    assert "unexpected-nodes" in inconsistent["issues"]
    source.write_bytes(original)
    (evidence / summary["nodes"][0]["terminal_ref"]).unlink()  # Disposable test evidence.
    review, _ = report(evidence, tmp_path / "out", exit_code=child.returncode, session_file=source)
    assert review["status"] == "incomplete"
    assert [n["evidence_verified"] for n in review["nodes"]] == [False, True]
