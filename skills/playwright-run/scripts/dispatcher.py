"""Dispatch selected formal nodes serially or under a task-scoped parallel instruction."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from ui_test_core.codex_dispatch_state import publish, read, transaction
from ui_test_core.artifact_layout import ProjectLayout, checked_path, dispatch_task_ref, short_id
from ui_test_core.path_utils import io_path
from ui_test_core.file_lock import FileLockBusy, exclusive_file_lock


from ui_test_core.suite import selected_suite

ENTRY = selected_suite().root / "scripts/codex_dispatch.py"
TASK_ENV = "UI_TEST_CODEX_TASK_REF"
PAUSED = 75


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def batch_signature(scope, extra, helper):
    values = [str(Path.cwd()), scope, extra, helper or None, os.environ.get("PYTEST_ADDOPTS", "")]
    if os.environ.get("UI_TEST_REQUIRE_FORMAL_V5") == "1":
        values.append("formal-v5")
    return digest(values)


def pytest_launch(task, batch_ref, scope, extra, helper, manifest, *, collect=False, run_id=None,
                  group=None, workers=0):
    args = [*scope, *extra, "-p", "ui_test_core.codex_pytest_dispatch", "--rootdir", str(Path.cwd())]
    args += ["--ui-batch-id", batch_ref]
    if collect:
        args.append("--collect-only")
    else:
        args.append("--ui-execution-origin=codex-cli")
        if run_id is not None:
            args += ["--ui-run-id", run_id]
    request = {"task_ref": dispatch_task_ref(task), "batch_ref": batch_ref,
               "scope": scope, "collect": collect, "manifest": str(manifest), "r2": "--ui-r2-approved" in extra}
    if os.environ.get("UI_TEST_REQUIRE_FORMAL_V5") == "1":
        # A project addopts setting cannot supply or replace a caller's reviewed limits.
        options = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        options.add_argument("--ui-write-budget")
        options.add_argument("--ui-write-budget-sha256")
        budget, _ = options.parse_known_args(extra)
        request["write_budget"] = [budget.ui_write_budget, budget.ui_write_budget_sha256]
        if request["r2"] and not all(request["write_budget"]):
            raise ValueError("E_FORMAL_BUDGET_REQUIRED")
    if group:
        request.update(group=group, workers=workers)
    env = dict(os.environ, UI_TEST_CODEX_REQUEST=json.dumps(request), UI_TEST_CODEX_TASK_REF=str(task))
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ENTRY.parent), env.get("PYTHONPATH"))))
    command = [sys.executable, helper, "--"] if helper else [sys.executable, "-m", "pytest"]
    return [*command, *args], env


def collect_manifest(task, batch_ref, scope, extra, helper):
    project = ProjectLayout.from_evidence(task) or ProjectLayout(task.parent)
    staging = project.temp_dir(short_id(dispatch_task_ref(task), batch_ref, "collection"))
    staging.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c-", dir=staging) as directory:
        manifest = Path(directory) / "collection.json"
        command, env = pytest_launch(task, batch_ref, scope, extra, helper, manifest, collect=True)
        exitcode = subprocess.run(command, env=env).returncode
        if exitcode or not manifest.is_file():
            raise ValueError(f"E_CODEX_COLLECTION_INCOMPLETE exit={exitcode}")
        return read(manifest)


def run_directory(task, run_id):
    old = task.parent / (task.name + ".runs") / run_id
    if io_path(old).is_dir():
        return old  # Continue an observer reserved before this layout was introduced.
    project = ProjectLayout.from_evidence(task) or ProjectLayout(task.parent)
    return project.temp_dir(short_id(dispatch_task_ref(task), run_id))


def observe_child(task, batch_ref, run_id, extra, helper):
    """Outlive the caller so a new dispatcher can recover the actual pytest exit."""
    folder = run_directory(task, run_id)
    with exclusive_file_lock(folder / "observer.lock", blocking=False):
        with transaction(task) as state:
            batch = state["batches"][batch_ref]
            row = batch["runs"][-1]
            if (state["active"] != batch_ref or batch["mode"] != "serial" or row["run_id"] != run_id or "pid" in row
                    or batch_signature(batch["selected"], extra, helper) != batch["signature"]):
                raise ValueError("E_CODEX_STALE_DISPATCH")
            command, env = pytest_launch(task, batch_ref, [row["node_id"]], extra, helper,
                                         folder / "collection.json", run_id=run_id)
            row["started_ns"] = time.time_ns()
            child = subprocess.Popen(command, env=env)
            row["pid"] = child.pid  # Child checks the reservation under this same lock.
        code = child.wait()
        publish(folder / "exit.json", {"run_id": run_id, "pid": child.pid, "exit": code, "exited_ns": time.time_ns()})


def reconcile(task, batch_ref, row):
    from ui_test_core.case_contracts import canonical_hash, validate_document
    from ui_test_core.session_evidence import verify_node_evidence

    folder = run_directory(task, row["run_id"])
    try:
        exit_record = read(folder / "exit.json")
        if (exit_record["run_id"], exit_record["pid"]) != (row["run_id"], row.get("pid")):
            raise ValueError("exit identity")
        row.update(pytest_exit=exit_record["exit"], exited_ns=exit_record["exited_ns"])
        manifest = read(folder / "collection.json")
        root = Path(manifest["evidence_root"])
        session_id = manifest["session_id"]
        session_path = root / "sessions" / (session_id + ".json")
        result = read(session_path)
        if validate_document(result, "pytest-session-result-v2.schema.json"):
            raise ValueError("session schema")
        session_hash = result.pop("session_result_hash")
        node, = result["nodes"]
        if (session_hash != canonical_hash(result) or result["session_id"] != session_id or result.get("batch_id") != batch_ref
                or result["expected_nodes"] != [row["node_id"]] or manifest["nodes"] != result["expected_nodes"]
                or (node.get("node_id"), node.get("run_id")) != (row["node_id"], row["run_id"])
                or result["pytest_exitstatus"] != row["pytest_exit"] or result.get("unexpected_nodes")
                or result.get("worker_errors") or not result.get("collection_consistent", True)
                or not verify_node_evidence(root, session_id, node)):
            raise ValueError("session or terminal identity")
        passed = (result["session_status"] == "passed" and row["pytest_exit"] == 0
                  and node["disposition"] == "passed" and result["all_required_nodes_committed"])
        row.update(session_ref=str(session_path), session_hash=session_hash,
                   node_result=node, disposition="passed" if passed else "failed")
        if manifest.get("r2") and not passed:
            if manifest.get("write_state") in (None, "submitted_unknown", "write_outcome_unknown"):
                row["disposition"] = "unknown"
    except (OSError, KeyError, ValueError, TypeError):
        row["disposition"] = "unknown"
    return row["disposition"]


def active_status(task, state):
    active = state["active"]
    if active is None:
        return None
    batch = state["batches"][active]
    if batch["mode"] == "parallel":
        from ui_test_core.codex_parallel_dispatch import reconcile_groups
        return reconcile_groups(task, state, active)
    for previous in batch["runs"][:-1]:
        if reconcile(task, active, previous) == "unknown":
            return "terminal-or-receipt-unconfirmed"
    row = batch["runs"][-1]
    folder = run_directory(task, row["run_id"])
    if not (folder / "exit.json").is_file():
        try:
            with exclusive_file_lock(folder / "observer.lock", blocking=False, existing_only=True):
                pass
        except FileLockBusy:
            return "running"
        except FileNotFoundError:
            pass
        return "exit-unconfirmed"
    if reconcile(task, active, row) == "unknown":
        return "terminal-or-receipt-unconfirmed"
    if len(batch["runs"]) == len(batch["nodes"]):
        batch["status"] = "passed" if all(r["disposition"] == "passed" for r in batch["runs"]) else "failed"
        state["active"] = None
    return None


def report_interruption(task, batch_ref, batch, reason):
    from ui_test_core.stage_delivery import formal_cases, recorded_origin, report_engine
    from ui_test_core.artifact_layout import batch_stage_id

    layout = ProjectLayout.from_evidence(batch.get("evidence_root", task)) or ProjectLayout(task.parent)
    stage_id = batch_stage_id(dispatch_task_ref(task), batch_ref)
    output = layout.reserve_run("playwright", stage_id)
    if (output / "report.html").exists() and not batch.get("interruption_report"):
        print(f"Previously delivered report: {(output / 'report.html').as_uri()}")
        return  # Preserve a finished delivery when its evidence is subsequently damaged.
    rows = {row["node_id"]: row for row in batch["runs"]}
    sessions = {}
    cases = []
    for node in batch["nodes"]:
        row = rows.get(node, {})
        owner = batch.get("owners", {}).get(node, {})
        case = dict(owner, node_id=node, status="unknown" if row else "not_executed", steps=[],
                    reason=reason if row else "批次中断，此节点尚未调度")
        if row.get("run_id"):
            case["run_id"] = row["run_id"]
        if row.get("session_hash") and row["disposition"] != "unknown":
            key = (row["session_ref"], row["session_hash"])
            if key not in sessions:
                sessions[key] = {c["node_id"]: c for c in formal_cases(key[0], session_hash=key[1], batch_id=batch_ref)}
            sealed = sessions[key][node]
            if sealed.get("run_id") != row.get("run_id"):
                raise ValueError("E_STAGE_BATCH_IDENTITY")
            case = sealed
        cases.append(case)
    _, engine = report_engine()
    delivery = engine.publish_stage_report("playwright", stage_id, cases, output,
                                           origin=recorded_origin(output, "playwright", stage_id))
    batch["interruption_report"] = True
    print(f"UI-Test stage report: {delivery['report_url']}")


def dispatch(task, batch_ref, scope, extra, helper, parallel_intent=None):
    if not task.is_absolute() or not re.fullmatch(r"[\w.-]{1,128}", batch_ref, re.ASCII):
        raise ValueError("E_CODEX_TASK_PATH_OR_BATCH_REF")
    task = task.resolve()
    checked_path(task, extra_units=5)  # The task journal's existing cross-process lock adds ".lock".
    checked_path(task.parent / ".ui-xxxxxxxx")  # The atomic journal file uses an independent temporary name.
    inherited = os.environ.get(TASK_ENV)
    if inherited and Path(inherited).resolve() != task:
        raise ValueError("E_CODEX_TASK_REF_MISMATCH")
    if helper:
        path = Path(helper).resolve(strict=True)
        if tuple(p.lower() for p in path.parts[-3:]) != ("helpers", "pycharm", "_jb_pytest_runner.py"):
            raise ValueError("E_CODEX_IDE_HELPER")
        helper = str(path)
    if any(arg.split("=", 1)[0] in {"--ui-run-id", "--ui-batch-id", "--"} for arg in extra):
        raise ValueError("E_CODEX_USE_BATCH_REF")
    for selector in scope:
        file = Path(selector.split("::", 1)[0])
        if file.suffix != ".py" or not file.is_file() or not file.resolve().is_relative_to(Path.cwd()):
            raise ValueError("E_CODEX_EXPLICIT_RUNNER_REQUIRED")
    signature = batch_signature(scope, extra, helper)
    if parallel_intent is not None:
        from ui_test_core.codex_parallel_dispatch import dispatch_parallel
        return dispatch_parallel(task, batch_ref, scope, extra, helper, parallel_intent, signature)
    with transaction(task) as state:
        existing = state["batches"].get(batch_ref)
    if existing is None:
        manifest = collect_manifest(task, batch_ref, scope, extra, helper)
        nodes = manifest["nodes"]
    while True:
        with transaction(task) as state:
            if batch_ref not in state["batches"]:
                state["batches"][batch_ref] = dict(signature=signature, project=str(Path.cwd()), mode="serial",
                                                   started_at=datetime.now(timezone.utc).isoformat(),
                                                   selected=scope, nodes=nodes, runs=[], status="pending",
                                                   evidence_root=manifest["evidence_root"], owners=dict(zip(nodes, manifest["owners"])))
                from ui_test_core.formal_catalog import begin_batch
                begin_batch(dispatch_task_ref(task), batch_ref, manifest, state["batches"][batch_ref]["started_at"])
            batch = state["batches"][batch_ref]
            if batch["signature"] != signature or batch["mode"] != "serial":
                raise ValueError("E_CODEX_BATCH_INPUT_CHANGED")
            if state["active"] not in (None, batch_ref):
                previous = active_status(task, state)
                if state["active"] is not None:
                    print(f"task {task}, active batch {state['active']}: {previous or 'pending previous batch'}")
                    return PAUSED
            if state["active"] is None and batch["status"] == "passed":
                state["active"], batch["status"] = batch_ref, "running"  # Verify a cached pass on resume.
            reason = active_status(task, state)
            if reason or state["active"] not in (None, batch_ref):
                if reason and reason != "running" and state["active"] == batch_ref:
                    report_interruption(task, batch_ref, batch, reason)
                print(f"task {task}, active batch {state['active']}: {reason or 'pending previous batch'}")
                return PAUSED
            if batch["status"] in {"passed", "failed"}:
                print(f"{batch['status']}: {task} / {batch_ref}")
                from ui_test_core.stage_delivery import publish_batch
                delivery = publish_batch(task, batch_ref, batch)
                batch.pop("interruption_report", None)
                print(f"UI-Test stage report: {delivery['report_url']}")
                return 0 if batch["status"] == "passed" else 1
            run_id = "UIT-" + uuid.uuid4().hex
            node = batch["nodes"][len(batch["runs"])]
            batch["runs"].append(dict(run_id=run_id, node_id=node, disposition="reserved"))
            state["active"], batch["status"] = batch_ref, "running"
            folder = run_directory(task, run_id)
            folder.mkdir(parents=True)
            # Reserve before spawning. A dead caller can never silently create a replacement run.
        watch = [sys.executable, str(ENTRY), "_observe", str(task), batch_ref, run_id, helper or "", *extra]
        with (folder / "pytest.log").open("w", encoding="utf-8") as log:
            code = subprocess.run(watch, stdout=log, stderr=subprocess.STDOUT).returncode
        if code:
            print(f"observer exit {code}; evidence {folder}")
            return PAUSED


def main():
    if sys.argv[1:2] == ["_observe-group"]:
        from ui_test_core.codex_parallel_dispatch import observe_group
        task, batch, group, helper, *extra = sys.argv[2:]
        observe_group(Path(task), batch, group, helper or None, extra)
        return 0
    if sys.argv[1:2] == ["_observe"]:
        task, batch, run, helper, *extra = sys.argv[2:]
        observe_child(Path(task), batch, run, extra, helper)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-ref", type=Path, default=os.environ.get(TASK_ENV), required=not os.environ.get(TASK_ENV))
    parser.add_argument("--batch-ref", required=True)
    parser.add_argument("--node", action="append", required=True)
    parser.add_argument("--ide-helper")
    parser.add_argument("--parallel-intent", type=Path, help="Explicit user instruction bound to this task, batch and complete node set")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    extra = options.pytest_args
    return dispatch(options.task_ref, options.batch_ref, options.node, extra[1:] if extra[:1] == ["--"] else extra,
                    options.ide_helper, options.parallel_intent)


def cli():
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
