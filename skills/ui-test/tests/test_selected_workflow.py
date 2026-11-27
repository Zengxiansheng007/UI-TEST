"""Offline owner-to-owner workflow through the same CLI used for an approved public batch."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT.parent


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(project, request, approved=True):
    name = project / "workflow-request.json"
    write(name, request)
    argv = [sys.executable, "-B", str(ROOT/"scripts/ui_test_suite.py"), "workflow", str(name)]
    if approved:
        argv += ["--approved-sha256", sha(name)]
    process = subprocess.run(argv, capture_output=True, timeout=360,
                             env=dict(os.environ, UI_TEST_SUITE=str(ROOT)))
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    if "E_WORKFLOW_FORMAL_INCOMPLETE" in result.get("reason", ""):
        print(process.stderr.decode("utf8", errors="replace"))
    return result


def prepare(project):
    source = json.loads((SKILLS/"plan/assets/playground-wizard.json").read_bytes())
    source["objective"] = "Read the controlled offline title"
    source["case"]["case_id"] = "CASE-STAGES"
    source["scope"]["risk_level"] = "r0-read-only"
    source["constraints"] = ["Read the local synthetic fixture only"]
    source["steps"] = [dict(step_id="check", action="assert", required=True,
                            risk_level="r0-read-only", postcondition="Read back fixture title")]
    source["run"]["run_id"] = "probe72"
    write(project/"source.json", source)
    (project/"explore.cjs").write_text("""
const {runExplorationStage} = require(process.env.UI_TEST_EXPLORE_ENTRY);
const cases = [{id:'CASE-STAGES',branch_id:'main',planSource:__filename,run(record) {
  record({step_id:'check',action:'Read fixture title',actual_result:'fixture title'});
}}];
runExplorationStage({cases,runId:process.env.UI_TEST_EXPLORATION_RUN_ID,
  outputRoot:process.env.UI_TEST_PROJECT,python:process.env.UI_TEST_PYTHON})
  .catch(e=>{console.error(e);process.exitCode=1;});
""", encoding="utf8")
    (project/"ui-test.project.yaml").write_bytes((ROOT/"assets/fixtures/specified-runner/project.json").read_bytes())
    hooks = (SKILLS/"playwright-run/tests/fixtures/read_only_hooks.py").read_text(encoding="utf8")
    (project/"conftest.py").write_text("from pathlib import Path\n"
        "pytest_plugins=['scripts.ui_test_core.pytest_runtime_plugin']\n"
        "def pytest_ui_test_execution_evidence_root(): return str(Path.cwd()/'evidence')\n" + hooks, encoding="utf8")
    (project/"test_local.py").write_text("import pytest, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0,{str(ROOT/'tests')!r})\nfrom test_stage_write_budget import session\n"
        "pytestmark=[pytest.mark.ui_test,pytest.mark.r0(formal_result=True),pytest.mark.case_id('CASE-STAGES'),"
        "pytest.mark.branch_id('main')]\n"
        "def test_fixture(ui_test_execution_context):\n"
        "    run=ui_test_execution_context.run_id\n    session(Path('runs')/run,None,run)\n"
        "    assert Path('title.txt').read_text() == 'fixture title'\n", encoding="utf8")
    (project/"title.txt").write_text("fixture title")
    req = dict(suite=str(ROOT),project=str(project),scope={"approval_ref":"#72 offline synthetic fixture only"},
               plan={"kind":"source","file":"source.json"}, explore=dict(run_id="probe72",runner="explore.cjs",
               files={n:sha(project/n) for n in ("source.json","explore.cjs")}))
    formal = dict(approval_ref="#72 read-only fixture", batch="approved", nodes=[dict(
        case_id="CASE-STAGES",branch_id="main",node="test_local.py::test_fixture")], checks=[dict(
        case_id="CASE-STAGES",branch_id="main",attempt_ref="1",step_id="check",expected={"visible_text":["fixture title"]})],
        files={n:sha(project/n) for n in ("test_local.py","ui-test.project.yaml","conftest.py","title.txt")})
    return req, formal


def test_continuation_and_interrupted_inputs(tmp_path):
    request, formal = prepare(tmp_path)
    assert call(tmp_path, request, approved=False)["reason"] == "E_WORKFLOW_APPROVAL_REQUIRED"
    assert not (tmp_path/"运行").exists()
    partial = call(tmp_path, request)
    assert partial.get("reason") == "E_WORKFLOW_FORMAL_MISSING", partial
    exp = partial["deliveries"]["explore"]
    assert Path(exp["report"]).is_file() and len(list(tmp_path.rglob("report.html"))) == 1
    formal["observations_sha256"] = exp["observations_sha256"]
    request["formal"] = formal
    formal["checks"][0]["expected"]["visible_text"] = ["wrong value"]
    mismatch = call(tmp_path, request)
    assert mismatch["reason"] == "E_WORKFLOW_VERIFICATION_FAILED" and mismatch["deliveries"]["explore"] == exp
    formal["checks"][0]["expected"]["visible_text"] = ["fixture title"]
    complete = call(tmp_path, request)
    assert complete["status"] == "completed", complete
    result = complete["deliveries"]["playwright-run"]
    assert Path(result["report"]).is_file() and len(list(tmp_path.rglob("report.html"))) == 2
    summary = json.loads(Path(result["report"]).with_name("execution-summary.json").read_bytes())
    row, = summary["cases"]
    assert row["case_id"] == "CASE-STAGES" and row["run_result_hash"] and row["status"] == "passed"
    before = Path(result["task"]).read_bytes()
    assert call(tmp_path, request)["status"] == "completed"
    assert Path(result["task"]).read_bytes() == before
