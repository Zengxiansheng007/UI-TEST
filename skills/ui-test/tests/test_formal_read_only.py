"""Real pytest transaction tests with a controlled in-memory row and no network."""
import json
from pathlib import Path

from scripts.ui_test_core.case_contracts import validate_document
from scripts.ui_test_core.finalization_transaction import FinalizationTransaction
from test_pytest_runtime_plugin import _PLUGIN_CONTEST, _V21_CONFIG_YAML

pytest_plugins = ["pytester"]


def test_read_only_formal_batch_commits_actual_assertions(pytester, monkeypatch):
    monkeypatch.setenv("PYTHONUTF8", "1")
    cfg = pytester.path / "ui-test.project.yaml"
    cfg.write_text(_V21_CONFIG_YAML, encoding="utf8")
    pytester.makeconftest(_PLUGIN_CONTEST + f'''
import json
from scripts.ui_test_core.case_contracts import canonical_hash
from scripts.ui_test_core.run_evidence_linker import build_run_result_v5, build_evidence_index_v2
def pytest_ui_test_project_config_path():
    return r"{cfg}"

def pytest_ui_test_finalization_target_v1(run_id, node_id, attempt_store):
    return {{"run_root": str(pathlib.Path.cwd() / "runs" / run_id)}}

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
        submit_count=0, step_results=[{{"step_id": "inspect-row", "status": status}}])
    return {{"run_result": result, "evidence_index": build_evidence_index_v2(result, run_result_ref="objects/pending.json")}}
''')
    runner = pytester.makepyfile(f'''
import sys
from pathlib import Path
import pytest
sys.path.insert(0, r"{Path(__file__).parent}")
from test_stage_write_budget import session

@pytest.mark.ui_test
@pytest.mark.case_id("CASE-STAGES")
@pytest.mark.branch_id("main")
@pytest.mark.r0(formal_result=True)
@pytest.mark.parametrize("expected", [pytest.param("visible target row", id="present"),
                                      pytest.param("absent row", id="absent"),
                                      pytest.param("visible target row", id="forged-boundary")])
def test_read_row(ui_test_execution_context, expected):
    ctx = ui_test_execution_context
    session(Path("runs") / ctx.run_id, None, ctx.run_id)
    assert ctx.approved is False
    assert "visible target row" == expected
''')
    result = pytester.runpytest_subprocess(str(runner), "--ui-batch-id", "READ-ROWS", "--ui-r2-approved")
    result.assert_outcomes(passed=2, failed=1, errors=1)
    assert "E_FINALIZATION_READ_ONLY_BOUNDARY_MISMATCH" in result.stdout.str()
    session_file, = (pytester.path / "evidence/sessions").glob("*.json")
    nodes = json.loads(session_file.read_text())["nodes"]
    report, = (pytester.path / "运行").rglob("execution-summary.json")
    cases = {c["node_id"]: c for c in json.loads(report.read_text(encoding="utf8"))["cases"]}
    footer = (report.parent/"report.html").read_text("utf8").split('<footer id="agent">', 1)[1]
    assert "来源未知" in footer and "本阶段证据索引" in footer and "执行时入口" in footer
    assert len(footer.split("<h3>")) - 1 == 3
    for node in nodes:
        root = pytester.path / "runs" / node["run_id"]
        closure = FinalizationTransaction(root).read_committed()
        if "forged-boundary" in node["node_id"]:
            assert node["disposition"] == "failed" and node["finalization_status"] == "failed"
            assert closure is None
            continue
        assert node["finalization_status"] == "committed"
        assert closure["receipt"]["status"] == "committed"
        v5 = closure["run_result"]
        context = json.loads((pytester.path / "evidence" / v5["execution_context_ref"]).read_text("utf8"))
        binding = context["binding"]
        assert binding["node_id"] == node["node_id"]
        assert (pytester.path / binding["entry"]).read_bytes() == runner.read_bytes()
        assert any(dep["source"] == "conftest.py" for dep in binding["dependencies"])
        assert v5["overall_status"] == v5["pytest_phase_status"]["call"] == node["disposition"]
        assert (v5["write_state"], v5["submit_count"]) == ("not_attempted", 0)
        assert cases[node["node_id"]]["run_result_hash"] == v5["run_result_hash"]
        boundary = json.loads((root / v5["approval_ref"]).read_text())
        assert boundary["max_submit_count"] == 0
        assert validate_document(dict(v5, write_state="write_succeeded_verified"), "run-result-v5.schema.json")
        assert validate_document(dict(v5, submit_count=1), "run-result-v5.schema.json")
        if v5["overall_status"] == "passed":
            legacy = dict(v5)
            del legacy["risk_level"]
            assert validate_document(legacy, "run-result-v5.schema.json")
