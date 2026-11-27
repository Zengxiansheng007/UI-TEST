import json
import os
from pathlib import Path
import subprocess
import sys

OWNER = Path(__file__).resolve().parents[1]
CORE = OWNER.with_name("ui-test")


def test_selected_formal_entry_owns_one_plugin_and_one_report(tmp_path):
    (tmp_path / "ui-test.project.yaml").write_bytes(
        (CORE / "assets/fixtures/specified-runner/project.json").read_bytes())
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\n"
        "pytest_plugins = ['scripts.ui_test_core.pytest_runtime_plugin']\n"
        "def pytest_ui_test_execution_evidence_root(): return str(Path.cwd() / 'evidence')\n"
        + (OWNER / "tests/fixtures/read_only_hooks.py").read_text(encoding="utf8"))
    (tmp_path / "test_local.py").write_text(
        "import pytest, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(CORE / 'tests')!r})\n"
        "from test_stage_write_budget import session\n"
        "pytestmark = [pytest.mark.ui_test, pytest.mark.r0(formal_result=True), pytest.mark.case_id('CASE-STAGES'), pytest.mark.branch_id('main')]\n"
        "def test_selected(ui_test_execution_context, pytestconfig):\n"
        "    from scripts.ui_test_core import pytest_runtime_plugin as old\n"
        "    from ui_test_core import pytest_runtime_plugin as current\n"
        "    session(Path('runs') / ui_test_execution_context.run_id, None, ui_test_execution_context.run_id)\n"
        "    assert old is current and old.__name__.endswith('capability_playwright_run.pytest_runtime_plugin')\n"
        "    assert old in pytestconfig.pluginmanager.get_plugins()\n"
        "    assert ui_test_execution_context.node_id.endswith('::test_selected')\n"
        "def test_excluded(): pytest.fail('unselected')\n")
    env = dict(os.environ, UI_TEST_SUITE=str(CORE),
               PYTHONPATH=os.pathsep.join(filter(None, [str(CORE), os.environ.get("PYTHONPATH")])))
    run = subprocess.run(
        [sys.executable, str(OWNER / "scripts/run.py"), "--task-ref", str(tmp_path / "formal.json"),
         "--batch-ref", "local", "--node", "test_local.py::test_selected"],
        cwd=tmp_path, env=env, capture_output=True, timeout=120)
    assert run.returncode == 0, (run.stdout, run.stderr)
    batch = json.loads((tmp_path / "formal.json").read_bytes())["batches"]["local"]
    assert batch["mode"] == "serial" and batch["nodes"] == ["test_local.py::test_selected"]
    report, = tmp_path.rglob("report.html")
    assert report.as_uri().encode() in run.stdout and "test_selected" in report.read_text(encoding="utf8")
    summary = json.loads(report.with_name("execution-summary.json").read_bytes())
    assert summary["cases"][0]["run_result_hash"] and summary["cases"][0]["status"] == "passed"
    terminal, = tmp_path.rglob("terminal.json")
    assert batch["runs"][0]["node_result"]["terminal_ref"].endswith(terminal.parent.name + "/terminal.json")
