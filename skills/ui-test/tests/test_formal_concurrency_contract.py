import json
from pathlib import Path

import pytest

from scripts.ui_test_core.pycharm_runtime import resolve_pycharm_run_context
from scripts.ui_test_core.project_config import ProjectConfigError, load_project_config


FIXTURE = Path(__file__).resolve().parents[1] / "assets/fixtures/specified-runner/project.json"


def test_legacy_default_and_explicit_serial_decision(tmp_path):
    project = tmp_path / "project.json"
    original = FIXTURE.read_bytes()
    project.write_bytes(original)
    baseline = load_project_config(project, purpose="execute")
    assert baseline["effective_concurrency"] == {"source": "legacy-template-default", "serial_constraints": []}
    decision = {"scope": "nodes", "node_ids": ["test_ui.py::test_save"], "decision_ref": "decision-42"}
    (tmp_path / "ui-test.serial-constraints.json").write_text(json.dumps([decision]))
    resolved = load_project_config(project, purpose="execute")
    assert resolved["effective_concurrency"] == {"source": "legacy-user-decision", "serial_constraints": [decision]}
    assert resolved["config_fingerprint"] == baseline["config_fingerprint"]
    assert project.read_bytes() == original
    bad = json.loads(original)
    bad["pycharm_manual_execution"]["r2_parallelism"] = "parallel"
    project.write_text(json.dumps(bad))
    with pytest.raises(ProjectConfigError, match="E_CONFIG_SCHEMA_INVALID"):
        load_project_config(project, purpose="execute")


def test_current_project_keeps_serial_decision_separate_from_r2_approval(tmp_path):
    template = FIXTURE.parents[2] / "project-v2.4.template.json"
    project = json.loads(template.read_text(encoding="utf-8"))
    assert project["schema_version"] == "2.4"
    decision = {"scope": "project-environment", "decision_ref": "review-23"}
    project["serial_constraints"] = [decision]
    path = tmp_path / "project.json"
    path.write_text(json.dumps(project))
    config = load_project_config(path, purpose="execute")
    assert config["effective_concurrency"] == {"source": "project-user-decision", "serial_constraints": [decision]}
    arguments = dict(config=config, case_id="CASE-A", branch_id="primary", node_id="test_ui.py::test_save",
                     risk_level="r2-ui-write-test", requested_run_id="RUN-23", explicitly_approved=False,
                     orig_argv=[], environ={})
    assert not resolve_pycharm_run_context(**arguments, argv=["pytest"])["approved"]
    runner = tmp_path / "helpers/pycharm/_jb_pytest_runner.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("# helper")
    assert resolve_pycharm_run_context(**arguments, argv=[str(runner)])["approved"]
