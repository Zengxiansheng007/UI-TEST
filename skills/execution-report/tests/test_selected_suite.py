import json
import os
from pathlib import Path
import subprocess
import sys

MAIN = Path(__file__).resolve().parents[2] / "ui-test"
CLI = MAIN / "scripts" / "ui_test_suite.py"


def invoke(*args, env=None):
    return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                          text=True, encoding="utf8", env=env)


def test_select_installation_and_reject_missing_and_ambiguous(tmp_path):
    ok = invoke("--suite", MAIN, "catalog")
    assert ok.returncode == 0, ok.stderr
    catalog = json.loads(ok.stdout)
    assert catalog["schema_version"] == 1
    assert "execution-report" in {entry["name"] for entry in catalog["entries"]}
    missing = invoke("--suite", tmp_path, "catalog")
    assert missing.returncode and "E_SUITE_MISSING" in missing.stderr
    other = tmp_path / "older" / "ui-test"
    other.mkdir(parents=True)
    ambiguous = invoke("catalog", env={**os.environ, "UI_TEST_SUITE": os.pathsep.join(map(str, [MAIN, other]))})
    assert ambiguous.returncode and str(other) in ambiguous.stderr


def test_relocated_report_is_loaded_only_from_selected_suite(tmp_path):
    from shutil import copytree, ignore_patterns

    main = tmp_path / "versions" / "v1" / "ui-test"
    owner = tmp_path / "capabilities" / "stage-reader"
    copytree(MAIN / "scripts", main / "scripts", ignore=ignore_patterns("__pycache__"))
    copytree(MAIN / "references", main / "references")
    copytree(MAIN.parent / "execution-report", owner, ignore=ignore_patterns("__pycache__"))
    (main / "references/suite-layout.json").write_text(json.dumps({"execution-report": str(owner)}))
    stage = tmp_path / "prior-stage"
    stage.mkdir()
    case = dict(case_id="CASE-A", node_id="A", attempt_ref="try-1", run_id=stage.name,
                status="observed", steps=[dict(step_id="S1", action="Review", status="observed")])
    original = stage / "observations.json"
    original.write_text(json.dumps(dict(stage="midscene", run_id=stage.name, cases=[case])))
    before = original.read_bytes()
    output = tmp_path / "reader-copy"
    result = invoke("--suite", main, "execution-report", "--observations", original, "--output", output)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    summary = json.loads(Path(receipt["execution_summary"]).read_text(encoding="utf8"))
    assert summary["run_id"] == "prior-stage" and summary["cases"][0]["attempt_ref"] == "try-1"
    assert Path(receipt["report_html"]).is_file() and Path(receipt["evidence_index"]).is_file()
    assert original.read_bytes() == before and list(stage.iterdir()) == [original]
    # The offline formal reader must validate the supplied session without loading the execution controller.
    bad_session = invoke("--suite", main, "execution-report", "--session", original, "--output", tmp_path / "bad-session")
    assert bad_session.returncode == 2 and bad_session.stderr.strip() == "E_STAGE_SESSION_IDENTITY"
    (main / "references/suite-layout.json").write_text(json.dumps({"execution-report": "absent"}))
    missing = invoke("--suite", main, "execution-report", "--observations", original, "--output", tmp_path / "missing")
    assert missing.returncode and "E_SUITE_CAPABILITY_MISSING" in missing.stderr


def test_relocated_plan_alias_reaches_its_actual_cli(tmp_path):
    import shutil

    main = tmp_path / "main" / "ui-test"
    scope = tmp_path / "elsewhere" / "planner"
    shutil.copytree(MAIN / "scripts", main / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(MAIN / "references", main / "references")
    shutil.copytree(MAIN / "schemas", main / "schemas")
    shutil.copytree(MAIN.parent / "plan", scope)
    (main / "references/suite-layout.json").write_text(json.dumps({"plan": str(scope)}))
    result = invoke("--suite", main, "resolve", "ui-test-plan")
    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert Path(resolved["skill"]) == scope
    output = tmp_path / "packet.json"
    run = subprocess.run([sys.executable, str(scope / "scripts/build_plan.py"), "--input",
                          str(scope / "assets/playground-wizard.json"), "--output", str(output)],
                         env={**os.environ, "PYTHONPATH": resolved["core_scripts"]}, capture_output=True)
    assert run.returncode == 0, run.stdout + run.stderr
    packet = json.loads(output.read_text(encoding="utf8"))
    assert packet["state"] == "plan" and packet["steps"]
