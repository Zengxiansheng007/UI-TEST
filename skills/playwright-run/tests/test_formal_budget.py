"""Exercise the dispatched pytest boundary with file-backed stand-ins for clicks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

OWNER = Path(__file__).resolve().parents[1]
CORE = OWNER.with_name("ui-test")


@pytest.mark.parametrize("interrupted", [False, True], ids=["completed", "interrupted"])
def test_batch_budget_stops_repeated_and_unlisted_clicks(tmp_path, monkeypatch, interrupted):
    monkeypatch.syspath_prepend(str(CORE/"scripts"))
    from ui_test_core.artifact_layout import dispatch_task_ref
    fixture = CORE/"assets/fixtures/specified-runner"
    (tmp_path/"project.json").write_bytes((fixture/"project.json").read_bytes())
    (tmp_path/"conftest.py").write_text((fixture/"conftest.py").read_text().replace(
        'root / "snapshot.json"', 'root / "reports/resolved-test-data.json"'))
    (tmp_path/"test_click.py").write_bytes((OWNER/"tests/fixtures/budget_case.py").read_bytes())
    node_a, node_b = "test_click.py::test_a", "test_click.py::test_b"
    row = dict(node=node_a, case_id="CASE-STAGES", branch_id="main", phases={"single": 1})
    nodes, limits = [node_a, node_b], [row]
    if interrupted:
        node_c = "test_click.py::test_c"
        nodes.append(node_c)
        limits.append(dict(node=node_c, case_id="CASE-C", branch_id="main", phases={"single": 1}))
    env = dict(os.environ, UI_TEST_SUITE=str(CORE), CONTROLLED_UI_EVIDENCE=str(tmp_path/"evidence"),
               PYTHONPATH=os.pathsep.join([str(CORE), str(CORE/"scripts"), str(CORE/"tests")]))
    budget = tmp_path/"budget.json"
    task = tmp_path/"task.json"
    batch = "one-batch"
    budget.write_text(json.dumps(dict(schema_version="ui-test.formal-write-budget.v1", batch=batch,
                                      task_ref=dispatch_task_ref(task), nodes=limits)))
    digest = hashlib.sha256(budget.read_bytes()).hexdigest()
    command = [sys.executable, str(OWNER/"scripts/run.py"), "--task-ref", str(task),
                          "--batch-ref", batch, *[arg for n in nodes for arg in ("--node", n)], "--", "--ui-r2-approved",
                          "--ui-write-budget", str(budget), "--ui-write-budget-sha256", digest]
    run = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, timeout=240)
    assert run.returncode != 0
    assert (tmp_path/"first.clicked").is_file() and (tmp_path/"exhausted.checked").is_file(), (run.stdout, run.stderr)
    assert not (tmp_path/"second.clicked").exists() and not (tmp_path/"unlisted.entered").exists()
    logs = [p.read_text(errors="replace") for p in tmp_path.rglob("pytest.log")]
    assert any("E_FORMAL_BUDGET_NODE" in log for log in logs), (run.stdout, run.stderr, logs)
    journal = json.loads(task.read_bytes())
    state = journal["batches"][batch]
    if interrupted:
        assert journal["active"] == batch and state["runs"][2]["disposition"] == "unknown"
    else:
        assert journal["active"] is None and state["status"] == "failed"
    assert state["runs"][1]["disposition"] == "not_executed"
    assert state["runs"][1]["node_result"]["missing_reason"] == "E_FORMAL_BUDGET_NODE"
    assert not state["runs"][1]["node_result"].get("attempt_ref")
    report, = tmp_path.rglob("execution-summary.json")
    cases = json.loads(report.read_bytes())["cases"]
    assert cases[0]["run_result_hash"] and cases[0]["status"] == "passed"
    assert cases[1]["status"] == "not_executed" and cases[1]["reason"] == "E_FORMAL_BUDGET_NODE"
    if interrupted:
        assert [c["node_id"] for c in cases] == nodes and cases[2]["status"] == "unknown"
    html = report.with_name("report.html")
    assert "E_FORMAL_BUDGET_NODE" in html.read_text(encoding="utf8") and html.as_uri().encode() in run.stdout
    again = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, timeout=240)
    assert again.returncode == run.returncode == (75 if interrupted else 1)
    assert json.loads(task.read_bytes()) == journal
    assert not (tmp_path/"unlisted.entered").exists()
    assert state["runs"][0]["disposition"] == "passed" and state["nodes"] == nodes


def test_project_batch_intersection_and_consumption_drift(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(CORE/"scripts"))
    from ui_test_core.formal_write_budget import ItemBudget, bind_item
    from dataclasses import replace
    from ui_test_core.stage_write_budget import make_budget
    path = tmp_path / "limits.json"
    row = dict(node="test.py::test_a", case_id="A", branch_id="main",
               phases={"review": 1, "save": 0, "outside": 1})
    path.write_text(json.dumps(dict(schema_version="ui-test.formal-write-budget.v1", batch="batch", task_ref="task", nodes=[row])))
    project = make_budget(dict(case_id="A", branch_id="main", phase_ids=["review", "save"]))
    item = ItemBudget(path, hashlib.sha256(path.read_bytes()).hexdigest(), "batch", "task", tmp_path/"permits",
                      "run", row["node"], "A", "main", tuple(project["phase_ids"]), project)
    with pytest.raises(ValueError, match="E_FORMAL_BUDGET_TASK"):
        replace(item, task_ref="other-task").check()
    with bind_item(item):
        for phase in ("outside", "save"):
            with pytest.raises(ValueError, match="E_FORMAL_BUDGET_PHASE"):
                item.reserve("run", "A", "main", phase, project)
        with pytest.raises(ValueError, match="E_FORMAL_BUDGET_PROJECT_PHASES"):
            item.reserve("run", "A", "main", "review", None)
        consume = item.reserve("run", "A", "main", "review", project)
        path.write_bytes(path.read_bytes() + b" ")
        with pytest.raises(ValueError, match="E_FORMAL_BUDGET_DIGEST"):
            consume()
    assert not list((tmp_path/"permits").glob("*.consumed"))

    # An independently reviewed task can reuse the same project, batch and node.
    other = json.loads(path.read_bytes())
    other["task_ref"] = "other-task"
    path.write_text(json.dumps(other))
    other_item = replace(item, task_ref="other-task", digest=hashlib.sha256(path.read_bytes()).hexdigest())
    with bind_item(other_item):
        other_item.reserve("run", "A", "main", "review", project)()
    assert len(list((tmp_path/"permits").glob("*.once"))) == 2


def test_formal_worker_launch_requires_explicit_budget_and_preserves_group_binding(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(CORE/"scripts"))
    monkeypatch.setenv("UI_TEST_SUITE", str(CORE))
    monkeypatch.setenv("UI_TEST_REQUIRE_FORMAL_V5", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--ui-write-budget injected.json --ui-write-budget-sha256 injected")
    from ui_test_core.suite import selected_suite
    from importlib import import_module
    package = selected_suite(CORE).load_package("playwright-run")
    launch = import_module(package.__name__ + ".dispatcher").pytest_launch
    prefix = (tmp_path/"task.json", "batch", ["test.py::test_local"])
    suffix = (None, tmp_path/"manifest.json")
    with pytest.raises(ValueError, match="E_FORMAL_BUDGET_REQUIRED"):
        launch(*prefix, ["--ui-r2-approved"], *suffix, collect=True)
    supplied = ["--ui-r2-approved", "--ui-write-budget", "reviewed.json", "--ui-write-budget-sha256", "reviewed"]
    _, env = launch(*prefix, supplied, *suffix, group="group", workers=2)
    request = json.loads(env["UI_TEST_CODEX_REQUEST"])
    assert request["workers"] == 2 and request["write_budget"] == ["reviewed.json", "reviewed"]

@pytest.mark.parametrize("case", [
    {"status": "passed", "run_id": "a-different-run"},
    {"status": "not_executed", "attempt_ref": "attempts/real"},
    {"status": "not_executed", "run_id": "a-different-run"},
])
def test_interruption_keeps_attempted_run_identity_strict(case, monkeypatch):
    monkeypatch.syspath_prepend(str(CORE/"scripts"))
    from ui_test_core.stage_delivery import verify_batch_run_identity
    with pytest.raises(ValueError, match="E_STAGE_BATCH_IDENTITY"):
        verify_batch_run_identity(case, {"run_id": "reserved-run", "disposition": "not_executed"})
