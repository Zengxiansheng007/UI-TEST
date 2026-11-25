import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
ENTRY = SKILL / "scripts/codex_dispatch.py"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "ui-test.project.yaml").write_bytes(
        (SKILL / "assets/fixtures/specified-runner/project.json").read_bytes())
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\n"
        "pytest_plugins = ('ui_test_core.pytest_runtime_plugin',)\n"
        "def pytest_ui_test_execution_evidence_root(): return str(Path.cwd() / 'evidence')\n"
        "def pytest_ui_test_project_config_path(): return str(Path.cwd() / 'ui-test.project.yaml')\n")
    (tmp_path / "test_sample.py").write_text(
        'import pytest\n'
        '@pytest.mark.ui_test\n@pytest.mark.r0\n@pytest.mark.case_id("CASE-A")\n'
        '@pytest.mark.branch_id("primary")\n@pytest.mark.parametrize("n", [1, 2])\n'
        'def test_value(n, ui_test_execution_context):\n'
        '    assert ui_test_execution_context.batch_ref == "batch"\n'
        '    assert ui_test_execution_context.node_id.endswith(f"[{n}]")\n')
    return tmp_path


def command(project, task="task", *extra):
    return [sys.executable, str(ENTRY), "--task-ref", str(project / (task + ".json")),
            "--batch-ref", "batch", "--node", "test_sample.py", *extra]


NODES = [f"test_sample.py::test_value[{n}]" for n in (1, 2)]


def parallel_command(project, method="auto", nodes=None, **fields):
    intent = dict(task_ref=str(project / "task.json"), batch_ref="batch",
                  instruction_ref="user-message/explicit-ab", nodes=nodes or NODES,
                  conflicts=[], method=method)
    intent.update(fields)
    path = project / "parallel.json"
    path.write_text(json.dumps(intent), encoding="utf-8")
    return command(project, "task", "--parallel-intent", str(path))


@pytest.mark.parametrize("method", ["auto", "independent"])
def test_parallel_dispatch_expands_and_records_exact_authorized_nodes(project, method):
    if method == "auto":
        pytest.importorskip("xdist")
    with (project / "test_sample.py").open("a") as sample:
        sample.write("""
    from pathlib import Path
    import time
    Path(f"started-{n}").touch()
    for _ in range(200):
        if Path(f"started-{3-n}").exists(): break
        time.sleep(0.05)
    assert Path(f"started-{3-n}").exists()
""")
    args = parallel_command(project, method)
    for _ in range(2):
        result = subprocess.run(args, cwd=project, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    assert batch["instruction_ref"] == "user-message/explicit-ab"
    assert batch["method"] == ("xdist" if method == "auto" else "independent")
    runs = batch["runs"]
    assert {row["node_id"] for row in runs} == set(NODES)
    assert len({row["run_id"] for row in runs}) == 2
    assert all(row["disposition"] == "passed" for row in runs)
    assert len({row["session_ref"] for row in runs}) == (1 if method == "auto" else 2)
    assert len(list((project / "evidence/attempts").iterdir())) == 2


def invoke(project, args, **env):
    return subprocess.run(args, cwd=project, env=dict(os.environ, **env), capture_output=True,
                          text=True, timeout=120)


def test_independent_tasks_with_same_batch_retain_reports_and_short_observer_files(project):
    long_name = "测" * (185 - len(str(project)))
    original = invoke(project, command(project, long_name))
    assert original.returncode == 0, original.stdout + original.stderr
    first, = project.glob("运行/p*/report.html")
    content = first.read_bytes()
    independent = invoke(project, command(project, "second"))
    assert independent.returncode == 0, independent.stdout + independent.stderr
    assert len(list(project.glob("运行/p*/report.html"))) == 2
    assert first.read_bytes() == content
    assert len(list(project.glob("临时/*/exit.json"))) == 4
    for item in project.glob("临时/**/*"):
        assert len(str(item).encode("utf-16-le")) // 2 <= 220


def test_serial_batch_publishes_one_offline_report_on_resume(project):
    urls = []
    for _ in range(2):
        result = invoke(project, command(project))
        assert result.returncode == 0, result.stdout + result.stderr
        link, = [line.split(": ", 1)[1] for line in result.stdout.splitlines()
                 if line.startswith("UI-Test stage report: ")]
        urls.append(link)
    html, = project.rglob("report.html")
    assert urls == [html.resolve().as_uri()] * 2
    document = html.read_text(encoding="utf8")
    for node in NODES:
        assert node in document
    assert len(list((project / "evidence/attempts").iterdir())) == 2


def test_parallel_instruction_cannot_expand_or_switch_tasks(project):
    escaped = invoke(project, parallel_command(project, nodes=[NODES[0]]))
    assert escaped.returncode == 2 and "E_CODEX_PARALLEL_NODE_SCOPE" in escaped.stderr
    switched = invoke(project, parallel_command(project, task_ref=str(project / "other.json")))
    assert switched.returncode == 2 and "E_CODEX_PARALLEL_INSTRUCTION_SCOPE" in switched.stderr
    assert not list((project / "evidence/attempts").glob("*"))


def test_auto_fallback_and_explicit_xdist_diagnostic(project):
    disabled = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    result = invoke(project, parallel_command(project, method="xdist"), **disabled)
    assert "E_CODEX_XDIST_UNAVAILABLE" in result.stderr
    explicit_cli = invoke(project, [*parallel_command(project), "--", "-n", "2", "--dist=load"], **disabled)
    assert explicit_cli.returncode == 2 and "E_CODEX_XDIST_UNAVAILABLE" in explicit_cli.stderr
    assert not list((project / "evidence/attempts").glob("*"))
    assert invoke(project, parallel_command(project), **disabled).returncode == 0
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    assert batch["method"] == "independent" and len(batch["groups"]) == 2


def test_conflict_holds_only_affected_nodes_and_reuses_exact_acceptance(project):
    sample = project / "test_sample.py"
    sample.write_text(sample.read_text().replace("[1, 2]", "[1, 2, 3]"))
    nodes = [*NODES, "test_sample.py::test_value[3]"]
    conflict = dict(writer=NODES[0], reader=NODES[1], object_ref="shared-todo/1",
                    write_action="complete", read_action="read remaining count",
                    assertion="remaining count is one", evidence_refs=["exploration/visible-count"])
    fields = dict(nodes=nodes, conflicts=[conflict])
    scope = dict(task_ref=str(project / "task.json"), batch_ref="batch", nodes=nodes)
    wrong = dict(scope=scope, conflict=dict(conflict, object_ref="shared-todo/2"), instruction_ref="decision-other")
    pending = invoke(project, parallel_command(project, acceptances=[wrong], **fields))
    assert pending.returncode == 75 and "remaining count is one" in pending.stdout
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    assert [row["node_id"] for row in batch["runs"]] == nodes[2:]
    current = dict(scope=scope, conflict=conflict, instruction_ref="decision/concrete-risk")
    assert invoke(project, parallel_command(project, acceptances=[current], **fields)).returncode == 0
    assert invoke(project, parallel_command(project, **fields)).returncode == 0
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    assert [v["instruction_ref"] for v in batch["accepted_conflicts"].values()] == ["decision/concrete-risk"]
    assert len(list((project / "evidence/attempts").iterdir())) == 3


def test_explicit_serial_decision_still_orders_the_parallel_batch(project):
    decision = dict(scope="nodes", node_ids=NODES, decision_ref="user-message/serial")
    (project / "ui-test.serial-constraints.json").write_text(json.dumps([decision]))
    result = invoke(project, parallel_command(project))
    assert result.returncode == 0, result.stdout + result.stderr
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    assert batch["serial_constraints"] == [decision]
    first, second = batch["runs"]
    assert first["exited_ns"] <= second["started_ns"]
    assert all(value in result.stdout for value in [*NODES, "nodes", decision["decision_ref"]])


def test_parallel_unknown_preserves_completed_neighbor_and_never_replays(project):
    with (project / "test_sample.py").open("a") as sample:
        sample.write("""
    from pathlib import Path
    import os
    if n == 2:
        with Path("spent").open("a") as log: log.write(str(n))
        os._exit(23)
""")
    args = parallel_command(project, method="independent")
    for _ in range(2):
        assert invoke(project, args).returncode == 75
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    assert [row["disposition"] for row in batch["runs"]] == ["passed", "unknown"]
    assert (project / "spent").read_text() == "2"


@pytest.mark.parametrize("dependency", ["independent", "serial-scope", "accepted-conflict"])
def test_parallel_unknown_only_holds_dependent_next_node(project, dependency):
    sample = project / "test_sample.py"
    nodes = [*NODES, "test_sample.py::test_value[3]"]
    sample.write_text(sample.read_text().replace("[1, 2]", "[1, 2, 3]") + """
    from pathlib import Path
    import os
    with Path(f"spent-{n}").open("a") as spent: spent.write("x")
    if n == 2: os._exit(23)
""")
    constraints = [dict(scope="nodes", node_ids=[nodes[0], nodes[2]], decision_ref="decision/a-c")]
    if dependency == "serial-scope":
        constraints.append(dict(scope="nodes", node_ids=nodes[1:], decision_ref="decision/b-c"))
    (project / "ui-test.serial-constraints.json").write_text(json.dumps(constraints))
    intent = {}
    if dependency == "accepted-conflict":
        conflict = dict(writer=nodes[1], reader=nodes[2], object_ref="shared-item", write_action="complete",
                        read_action="count", assertion="remaining item", evidence_refs=["explore/item"])
        scope = dict(task_ref=str(project / "task.json"), batch_ref="batch", nodes=nodes)
        intent = dict(conflicts=[conflict], acceptances=[dict(scope=scope, conflict=conflict, instruction_ref="risk/ok")])
    args = parallel_command(project, method="independent", nodes=nodes, **intent)
    for _ in range(2):
        assert invoke(project, args).returncode == 75
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    expected = ["passed", "unknown", "passed"] if dependency == "independent" else ["passed", "unknown"]
    assert [r["disposition"] for r in batch["runs"]] == expected
    assert all(path.read_text() == "x" for path in project.glob("spent-*"))
    if dependency == "independent":
        first, crashed, last = batch["runs"]
        assert max(first["exited_ns"], crashed["exited_ns"]) <= last["started_ns"]


@pytest.mark.parametrize("mode", ["serial", "parallel"])
def test_completed_dispatch_rechecks_evidence_without_restarting(project, mode):
    args = command(project) if mode == "serial" else parallel_command(project, method="independent")
    assert invoke(project, args).returncode == 0
    task = project / "task.json"
    first, second = json.loads(task.read_text())["batches"]["batch"]["runs"]
    terminal = project / "evidence" / first["node_result"]["terminal_ref"]
    original = terminal.read_bytes()
    terminal.unlink()
    assert invoke(project, args).returncode == 75
    batch = json.loads(task.read_text())["batches"]["batch"]
    assert batch["status"] != "passed" and [r["run_id"] for r in batch["runs"]] == [first["run_id"], second["run_id"]]
    terminal.write_bytes(original)
    assert invoke(project, args).returncode == 0
    assert len(list((project / "evidence/attempts").iterdir())) == 2


def test_serial_file_expansion_and_duplicate_batch(project):
    pytest.importorskip("xdist")
    (project / "pytest.ini").write_text("[pytest]\naddopts = -n auto\n")
    env = dict(os.environ, PYTEST_ADDOPTS="-n auto")
    args = command(project, "task", "--", "-n", "auto")
    for _ in range(2):  # A repeated delivery returns the saved batch and spends no new runs.
        result = subprocess.run(args, cwd=project, env=env, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    first, second = batch["runs"]
    assert [first["node_id"], second["node_id"]] == [
        "test_sample.py::test_value[1]", "test_sample.py::test_value[2]"]
    assert first["exited_ns"] <= second["started_ns"]
    assert len(list((project / "evidence/attempts").iterdir())) == 2
    assert all(row["disposition"] == "passed" and Path(row["session_ref"]).is_file()
               for row in (first, second))


def test_interrupted_dispatcher_and_independent_task(project):
    sample = project / "test_sample.py"
    sample.write_text(sample.read_text() + """
    import os, time
    from pathlib import Path
    if n == 1 and os.environ.get("HOLD_TEST"):
        Path("holding").touch()
        for _ in range(900):
            if Path("released").exists(): break
            time.sleep(0.1)
        else: pytest.fail("timed out waiting for independent task")
""")
    args = command(project)
    with (project / "first.log").open("w") as log:
        caller = subprocess.Popen(args, cwd=project, env=dict(os.environ, HOLD_TEST="1"),
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_for(lambda: (project / "holding").exists() or caller.poll() is not None)
            assert (project / "holding").exists(), (project / "first.log").read_text()
            caller.terminate()  # The observer and the running pytest retain their own process handles.
            caller.wait(timeout=15)
            assert subprocess.run(args, cwd=project, timeout=60).returncode == 75
            assert subprocess.run(command(project, "independent"), cwd=project, timeout=90).returncode == 0
            assert not (project / "released").exists()
        finally:
            (project / "released").touch()
            if caller.poll() is None:
                caller.wait(timeout=60)
    held_id = json.loads((project / "task.json").read_text())["batches"]["batch"]["runs"][0]["run_id"]
    wait_for(lambda: any(json.loads(f.read_text())["run_id"] == held_id for f in (project / "临时").glob("*/exit.json")))
    assert subprocess.run(args, cwd=project, timeout=90).returncode == 0
    rows = json.loads((project / "task.json").read_text())["batches"]["batch"]["runs"]
    assert len(rows) == 2 and rows[0]["exited_ns"] <= rows[1]["started_ns"]
    assert len(list((project / "evidence/attempts").iterdir())) == 4


def wait_for(check):
    deadline = time.monotonic() + 80
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.1)
    pytest.fail("expected child process event was missing")


def test_missing_terminal_preserves_unknown_run_and_remaining_node(project):
    sample = project / "test_sample.py"
    sample.write_text(sample.read_text() + """
    import os
    from pathlib import Path
    with Path("dispatch-count").open("a") as log: log.write(str(n))
    os._exit(23)
""")
    for _ in range(2):
        assert subprocess.run(command(project), cwd=project, timeout=90).returncode == 75
    batch = json.loads((project / "task.json").read_text())["batches"]["batch"]
    assert len(batch["runs"]) == 1 and batch["runs"][0]["disposition"] == "unknown"
    assert (project / "dispatch-count").read_text() == "1"


def test_indirect_ide_inherits_parent_task_and_cannot_switch_task(project):
    helper = os.environ.get("UI_TEST_IDE_HELPER")
    if not helper:
        pytest.skip("set UI_TEST_IDE_HELPER to the installed JetBrains pytest helper")
    task = project / "task.json"
    env = dict(os.environ, UI_TEST_CODEX_TASK_REF=str(task))
    switched = subprocess.run(command(project, "different"), env=env, cwd=project,
                              capture_output=True, text=True, timeout=60)
    assert "E_CODEX_TASK_REF_MISMATCH" in switched.stderr
    result = subprocess.run([sys.executable, str(ENTRY), "--batch-ref", "batch", "--ide-helper", helper,
                             "--node", "test_sample.py::test_value[1]"], cwd=project, env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    run, = json.loads(task.read_text())["batches"]["batch"]["runs"]
    session = json.loads(Path(run["session_ref"]).read_text())
    assert session["execution_origin"] == "pycharm"
    context_path = (project / "evidence" / run["node_result"]["terminal_ref"]).with_name("execution-context.json")
    context = json.loads(context_path.read_text())
    assert context["task_ref"].startswith("CODEX-") and context["batch_ref"] == "batch"
    assert context["approval_source"] == "not-approved"
    sample = project / "test_sample.py"
    sample.write_text(sample.read_text().replace("@pytest.mark.r0", "@pytest.mark.r2"))
    denied = subprocess.run([sys.executable, str(ENTRY), "--batch-ref", "needs-approval", "--ide-helper", helper,
                             "--node", "test_sample.py"], cwd=project, env=env, capture_output=True, text=True, timeout=90)
    assert denied.returncode and "E_CODEX_EXPLICIT_R2_APPROVAL_REQUIRED" in (denied.stdout + denied.stderr)
    assert len(list((project / "evidence/attempts").iterdir())) == 1


def test_failure_receipt_without_a_known_write_outcome_pauses_the_task(project):
    sample = project / "test_sample.py"
    sample.write_text(sample.read_text().replace("@pytest.mark.r0", "@pytest.mark.r2") + """
    from pathlib import Path
    with Path("spent").open("a") as log: log.write(str(n))
""")
    with (project / "conftest.py").open("a") as hooks:
        hooks.write("""
def pytest_ui_test_finalization_target_v1(run_id, node_id, attempt_store):
    return {"run_root": str(Path.cwd() / "runs" / run_id)}
def pytest_ui_test_build_finalization_candidate_v1(run_id, node_id, transaction_id,
        pre_terminal_events_hash, pytest_phase_status, attempt_store):
    raise OSError("synthetic write outcome unavailable")
""")
    denied = subprocess.run(command(project), cwd=project, capture_output=True, text=True, timeout=90)
    assert denied.returncode and "E_CODEX_EXPLICIT_R2_APPROVAL_REQUIRED" in denied.stderr
    assert not (project / "spent").exists()
    allowed = command(project, "task", "--", "--ui-r2-approved")
    for _ in range(2):
        assert subprocess.run(allowed, cwd=project, timeout=90).returncode == 75
    row, = json.loads((project / "task.json").read_text())["batches"]["batch"]["runs"]
    assert row["node_result"]["finalization_status"] == "failed" and row["node_result"]["receipt_hash"]
    assert row["disposition"] == "unknown" and (project / "spent").read_text() == "1"
