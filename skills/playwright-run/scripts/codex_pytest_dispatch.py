"""Check the merged pytest inputs and publish the exact formal collection before fixtures."""
import json
import os
import time
from pathlib import Path

import pytest

from ui_test_core.codex_dispatch_state import publish, read, transaction


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_cmdline_main(config):
    # 在 xdist 解释合并后的项目、环境和 CLI 选项前固定本次调度。
    if hasattr(config, "workerinput"):
        return (yield)  # worker 沿用 xdist 已固定的单进程选项。
    request = json.loads(os.environ["UI_TEST_CODEX_REQUEST"])
    workers = request.get("workers", 0)
    if hasattr(config.option, "numprocesses"):
        if getattr(config.option, "px", []) or getattr(config.option, "looponfail", False):
            raise pytest.UsageError("E_CODEX_UNSUPPORTED_WORKER_OPTIONS")
        config.option.numprocesses = workers
        config.option.dist = "load" if workers else "no"
        config.option.distload = False
        config.option.tx = []
    elif workers:
        raise pytest.UsageError("E_CODEX_XDIST_UNAVAILABLE")
    return (yield)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    config = session.config
    request = json.loads(os.environ["UI_TEST_CODEX_REQUEST"])
    option = config.option
    workers = request.get("workers", 0)
    worker = getattr(config, "workerinput", None)
    if workers and worker is None:
        if (option.numprocesses != workers or option.dist != "load"
                or option.tx != ["popen"] * workers):
            raise pytest.UsageError("E_CODEX_PARALLEL_EFFECTIVE_OPTIONS")
    elif not workers and (getattr(option, "numprocesses", 0) or getattr(option, "dist", "no") != "no"
                          or getattr(option, "tx", []) or worker is not None):
        raise pytest.UsageError("E_CODEX_SERIAL_EFFECTIVE_OPTIONS")
    if (getattr(option, "reruns", 0) or getattr(option, "count", 1) not in (1, None)
            or getattr(option, "looponfail", False)):
        raise pytest.UsageError("E_CODEX_REPEATED_EXECUTION")
    if bool(option.collectonly) != request["collect"] or config.args != request["scope"]:
        raise pytest.UsageError("E_CODEX_DISPATCH_SCOPE")
    if not hasattr(config, "_ui_test_dispatch_session"):
        raise pytest.UsageError("E_CODEX_FORMAL_PLUGIN_REQUIRED")
    if not request["collect"]:
        with transaction(os.environ["UI_TEST_CODEX_TASK_REF"]) as state:
            if state["active"] != request["batch_ref"]:
                raise pytest.UsageError("E_CODEX_TASK_NOT_ACTIVE")
            batch = state["batches"][state["active"]]
            if "group" in request:
                group = batch["groups"].get(request["group"], {})
                pid = worker.get("codex_controller_pid") if worker else os.getpid()
                if (batch["mode"] != "parallel" or group.get("status") != "running"
                        or group.get("pid") != pid or group.get("nodes") != request["scope"]
                        or workers != group.get("workers") or group.get("run_id") != config.getoption("--ui-run-id")
                        or (worker and os.getppid() != pid)):
                    raise pytest.UsageError("E_CODEX_PROCESS_NOT_DISPATCHED")
            else:
                run = batch["runs"][-1]
                if (batch["mode"] != "serial" or run.get("pid") != os.getpid() or run["run_id"] != config.getoption("--ui-run-id")
                        or request["scope"] != [run["node_id"]]):
                    raise pytest.UsageError("E_CODEX_PROCESS_NOT_DISPATCHED")
    config._ui_test_codex_request = request
    if workers and worker is None:
        root = config.hook.pytest_ui_test_execution_evidence_root()
        if not root:
            raise pytest.UsageError("E_CODEX_EVIDENCE_ROOT_REQUIRED")
        publish(request["manifest"], dict(nodes=request["scope"], session_id=config._ui_test_dispatch_session,
                                          evidence_root=str(Path(root).resolve())))


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    node.workerinput["codex_controller_pid"] = os.getpid()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    request = item.config._ui_test_codex_request
    if "group" not in request:
        return
    with transaction(os.environ["UI_TEST_CODEX_TASK_REF"]) as state:
        batch = state["batches"][request["batch_ref"]]
        if state["active"] != request["batch_ref"]:
            raise pytest.UsageError("E_CODEX_TASK_NOT_ACTIVE")
        for row in batch["runs"]:
            if row["group"] == request["group"] and row["node_id"] == item.nodeid:
                if "started_ns" in row:
                    raise pytest.UsageError("E_CODEX_REPEATED_EXECUTION")
                row.update(started_ns=time.time_ns(), execution_pid=os.getpid(), disposition="started")
                return
        raise pytest.UsageError("E_CODEX_UNEXPECTED_EXECUTION_SCOPE")


def pytest_collection_finish(session):
    config = session.config
    request = config._ui_test_codex_request
    items = [item for item in session.items if item.get_closest_marker("ui_test")]
    nodes = [item.nodeid for item in items]
    if not nodes or len(nodes) != len(set(nodes)):
        raise pytest.UsageError("E_CODEX_EMPTY_OR_DUPLICATE_FORMAL_SCOPE")
    if not request["collect"] and (nodes != request["scope"] or len(session.items) != len(nodes)):
        raise pytest.UsageError("E_CODEX_UNEXPECTED_EXECUTION_SCOPE")
    if any(item.get_closest_marker("flaky") for item in items) and config.pluginmanager.hasplugin("rerunfailures"):
        raise pytest.UsageError("E_CODEX_REPEATED_EXECUTION")
    if os.environ.get("UI_TEST_REQUIRE_FORMAL_V5") == "1":
        from .pytest_runtime_plugin import _formal_read_only
        if any(not (_formal_read_only(item) or item.get_closest_marker("r2")) for item in items):
            raise pytest.UsageError("E_FORMAL_V5_NODE_REQUIRED")
        if getattr(config.option, "ui_pre_submit_only", False):
            raise pytest.UsageError("E_FORMAL_V5_NODE_REQUIRED")
    has_write = any(item.get_closest_marker("r2") for item in items)
    if has_write and not request["r2"]:
        raise pytest.UsageError("E_CODEX_EXPLICIT_R2_APPROVAL_REQUIRED")
    root = config.hook.pytest_ui_test_execution_evidence_root()
    if not root:
        raise pytest.UsageError("E_CODEX_EVIDENCE_ROOT_REQUIRED")
    if hasattr(config, "workerinput"):
        return  # worker 只校验实际收集集合，controller 独占汇总文件。
    manifest = {"nodes": nodes, "r2": has_write, "session_id": config._ui_test_dispatch_session,
                "evidence_root": str(Path(root).resolve())}
    if request["collect"]:
        from ui_test_core.formal_catalog import selected_cases
        manifest["owners"] = selected_cases(items)
        from ui_test_core.project_config import load_project_config
        project = load_project_config(config.hook.pytest_ui_test_project_config_path(), purpose="execute")
        manifest.update(r2_nodes=[item.nodeid for item in items if item.get_closest_marker("r2")],
                        xdist=config.pluginmanager.hasplugin("xdist") or config.pluginmanager.hasplugin("xdist.plugin"),
                        serial_constraints=project["effective_concurrency"]["serial_constraints"])
    publish(request["manifest"], manifest)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session):
    outcome = yield
    config = session.config
    if hasattr(config, "_ui_test_codex_write_state") and not hasattr(config, "workerinput"):
        path = config._ui_test_codex_request["manifest"]
        manifest = read(path)
        manifest["write_states"] = config._ui_test_codex_write_state
        if len(manifest["nodes"]) == 1:
            manifest["write_state"] = manifest["write_states"].get(manifest["nodes"][0])
        publish(path, manifest)
    return outcome
