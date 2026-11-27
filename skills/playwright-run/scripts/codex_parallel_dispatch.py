"""Schedule precisely the formal nodes covered by a current user instruction."""
import importlib.util
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .dispatcher import (ENTRY, PAUSED, active_status, batch_signature, collect_manifest,
                            digest, pytest_launch, report_interruption, run_directory)
from ui_test_core.case_contracts import canonical_hash, validate_document
from ui_test_core.codex_dispatch_state import publish, read, transaction
from ui_test_core.file_lock import FileLockBusy, exclusive_file_lock
from ui_test_core.session_evidence import verify_node_evidence
from ui_test_core.shared_state_conflict import Acceptance, Conflict, Scope, accepted_instruction


def references(values):
    if (not isinstance(values, list) or not values or len(values) != len(set(values))
            or not all(isinstance(value, str) and value.strip() for value in values)):
        raise ValueError("E_CODEX_PARALLEL_REFERENCES")
    return values


def parse_conflict(data):
    fields = dict(data)
    fields["evidence_refs"] = tuple(references(fields["evidence_refs"]))
    conflict = Conflict(**fields)
    if (conflict.writer == conflict.reader or
            not all(isinstance(v, str) and v.strip() for k, v in fields.items() if k != "evidence_refs")):
        raise ValueError("E_CODEX_CONCRETE_CONFLICT_REQUIRED")
    return conflict


def parse_intent(path, task, batch_ref):
    try:
        data = read(path)
        nodes = references(data["nodes"])
        scope = Scope(str(task), batch_ref, frozenset(nodes))
        if (not Path(data["task_ref"]).is_absolute() or Path(data["task_ref"]).resolve() != task
                or data["batch_ref"] != batch_ref or not isinstance(data["instruction_ref"], str)
                or not data["instruction_ref"].strip() or data.get("method", "auto") not in {"auto", "xdist", "independent"}
                or not isinstance(data["conflicts"], list) or not isinstance(data.get("acceptances", []), list)):
            raise ValueError("E_CODEX_PARALLEL_INSTRUCTION_SCOPE")
        conflicts = [parse_conflict(row) for row in data["conflicts"]]
        decisions = []
        for row in data.get("acceptances", []):
            declared = row["scope"]
            decision_scope = Scope(declared["task_ref"], declared["batch_ref"], frozenset(references(declared["nodes"])))
            if not isinstance(row["instruction_ref"], str) or not row["instruction_ref"].strip():
                raise ValueError("E_CODEX_CONFLICT_DECISION_REF")
            decisions.append(Acceptance(decision_scope, parse_conflict(row["conflict"]), row["instruction_ref"]))
        return data, scope, conflicts, decisions
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("E_CODEX_PARALLEL_INSTRUCTION_FORMAT") from exc


def conflict_key(conflict):
    fields = asdict(conflict)
    fields.pop("evidence_refs")  # Additional evidence does not change the user's decision.
    return digest(fields)


def held_nodes(batch, scope, conflicts, decisions):
    pending = []
    held = set()
    for conflict in conflicts:
        affected = {conflict.writer, conflict.reader}
        if not affected <= scope.nodes:
            continue
        key = conflict_key(conflict)
        instruction = accepted_instruction(scope, conflict, decisions)
        if instruction:
            batch["accepted_conflicts"].setdefault(key, dict(conflict=asdict(conflict), instruction_ref=instruction))
        if key not in batch["accepted_conflicts"]:
            pending.append(asdict(conflict))
            held.update(affected)
    batch["pending_conflicts"] = pending
    return held


def select_wave(batch, held, conflicts):
    spent = {row["node_id"] for row in batch["runs"]}
    unknown = {row["node_id"] for row in batch["runs"] if row["disposition"] == "unknown"}
    for conflict in conflicts:
        affected = {conflict.writer, conflict.reader}
        if affected & unknown:
            held.update(affected)
    ready = []
    occupied = {index for index, decision in enumerate(batch["serial_constraints"])
                if unknown.intersection(decision.get("node_ids") or batch["nodes"])}
    for node in batch["nodes"]:
        if node in held or node in spent:
            continue
        scopes = {index for index, decision in enumerate(batch["serial_constraints"])
                  if not decision.get("node_ids") or node in decision["node_ids"]}
        if not occupied.intersection(scopes):
            ready.append(node)
            occupied.update(scopes)
    return ready


def reserve_groups(task, batch, ready):
    groups = []
    selections = [ready] if batch["method"] == "xdist" else [[node] for node in ready]
    for nodes in selections:
        identity = "GROUP-" + uuid.uuid4().hex
        workers = min(len(nodes), batch["max_workers"]) if len(nodes) > 1 else 0
        run_id = None if workers else "UIT-" + uuid.uuid4().hex
        batch["groups"][identity] = dict(nodes=nodes, workers=workers, run_id=run_id, status="reserved")
        batch["runs"].extend(dict(node_id=node, group=identity, run_id=run_id, disposition="reserved") for node in nodes)
        run_directory(task, identity).mkdir(parents=True)
        groups.append(identity)
    return groups


def observe_group(task, batch_ref, identity, helper, extra):
    folder = run_directory(task, identity)
    with exclusive_file_lock(folder / "observer.lock", blocking=False):
        with transaction(task) as state:
            batch = state["batches"][batch_ref]
            group = batch["groups"][identity]
            if (state["active"] != batch_ref or group["status"] != "reserved"
                    or batch["signature"] != batch_signature(batch["selected"], extra, helper)):
                raise ValueError("E_CODEX_STALE_DISPATCH")
            args, env = pytest_launch(task, batch_ref, group["nodes"], extra, helper, folder / "collection.json",
                                      run_id=group["run_id"], group=identity, workers=group["workers"])
            started = time.time_ns()
            child = subprocess.Popen(args, env=env)
            group.update(status="running", pid=child.pid, started_ns=started)
        code = child.wait()
        publish(folder / "exit.json", dict(group=identity, pid=child.pid, exit=code, exited_ns=time.time_ns()))


def verify_group(folder, group, batch_ref, rows, r2_nodes):
    manifest = read(folder / "collection.json")
    root = Path(manifest["evidence_root"])
    session_id = manifest["session_id"]
    path = root / "sessions" / (session_id + ".json")
    result = read(path)
    if validate_document(result, "pytest-session-result-v2.schema.json"):
        raise ValueError("session schema")
    session_hash = result.pop("session_result_hash")
    if (session_hash != canonical_hash(result) or result["session_id"] != session_id
            or result.get("batch_id") != batch_ref or manifest["nodes"] != group["nodes"]
            or result["expected_nodes"] != group["nodes"] or result["pytest_exitstatus"] != group["pytest_exit"]):
        raise ValueError("session or process identity")
    entries = {node["node_id"]: node for node in result["nodes"]}
    if len(entries) != len(result["nodes"]) or set(entries) != set(group["nodes"]):
        raise ValueError("session node identity")
    run_ids = [node["run_id"] for node in entries.values() if node.get("run_id")]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("duplicate run identity")
    for row in rows:
        node_id = row["node_id"]
        node = entries[node_id]
        row.update(session_ref=str(path), session_hash=session_hash, node_result=node,
                   pid=group["pid"], exited_ns=group["exited_ns"], pytest_exit=group["pytest_exit"])
        if verify_node_evidence(root, session_id, node) and (not group["run_id"] or node["run_id"] == group["run_id"]):
            row.update(run_id=node["run_id"], disposition=node["disposition"])
            if node_id in r2_nodes and node["disposition"] != "passed":
                if manifest.get("write_states", {}).get(node_id) in (None, "submitted_unknown", "write_outcome_unknown"):
                    row["disposition"] = "unknown"
        elif node["disposition"] == "not_executed" and node.get("missing_reason") and not node.get("attempt_ref"):
            row["disposition"] = "not_executed"
        else:
            row["disposition"] = "unknown"
    if any(row["disposition"] == "unknown" for row in rows):
        return "unknown"
    if (group["pytest_exit"] == 0 and result["session_status"] == "passed" and result["all_required_nodes_committed"]
            and not result["worker_errors"] and not result["unexpected_nodes"] and result["collection_consistent"]
            and not result.get("denied_duplicate_nodes") and all(row["disposition"] == "passed" for row in rows)):
        return "passed"
    return "failed"


def reconcile_groups(task, state, batch_ref, *, resume_same_batch=False):
    batch = state["batches"][batch_ref]
    reasons = []
    for identity, group in batch["groups"].items():
        folder = run_directory(task, identity)
        rows = [row for row in batch["runs"] if row["group"] == identity]
        if not (folder / "exit.json").is_file():
            try:
                with exclusive_file_lock(folder / "observer.lock", blocking=False, existing_only=True):
                    pass
            except FileLockBusy:
                reasons.append("running")
                continue
            except FileNotFoundError:
                pass
            reasons.append("exit-unconfirmed")
            continue
        try:
            exit_record = read(folder / "exit.json")
            if (exit_record["group"] != identity or not isinstance(group.get("pid"), int)
                    or exit_record["pid"] != group["pid"]
                    or not isinstance(exit_record["exit"], int) or not isinstance(exit_record["exited_ns"], int)):
                raise ValueError("exit identity")
            group.update(pytest_exit=exit_record["exit"], exited_ns=exit_record["exited_ns"])
        except (OSError, ValueError, KeyError, TypeError):
            reasons.append("exit-unconfirmed")
            continue
        for row in rows:
            row.update(pid=group["pid"], pytest_exit=group["pytest_exit"], exited_ns=group["exited_ns"])
        try:
            group["status"] = verify_group(folder, group, batch_ref, rows, batch["r2_nodes"])
        except (OSError, ValueError, KeyError, TypeError):
            group["status"] = "unknown"
            for row in rows:
                row["disposition"] = "unknown"
    if reasons:
        batch["status"] = "running" if all(reason == "running" for reason in reasons) else "exit-unconfirmed"
        return ", ".join(dict.fromkeys(reasons))
    if any(group["status"] == "unknown" for group in batch["groups"].values()):
        batch["status"] = "evidence-unconfirmed"
        if not resume_same_batch:
            return "terminal-or-receipt-unconfirmed"
    elif len(batch["runs"]) == len(batch["nodes"]):
        batch["status"] = "passed" if all(g["status"] == "passed" for g in batch["groups"].values()) else "failed"
        state["active"] = None
    return None


def scheduler_options(requested, extra):
    remaining = []
    workers = 2
    options = iter(extra)
    for arg in options:
        if arg in ("-n", "--numprocesses", "--dist"):
            value = next(options, None)
        elif arg.startswith(("--numprocesses=", "--dist=")):
            value = arg.partition("=")[2]
        elif arg.startswith("-n") and len(arg) > 2:
            value = arg[2:]
        else:
            remaining.append(arg)
            continue
        if requested == "independent" or not value:
            raise ValueError("E_CODEX_PARALLEL_METHOD_CONFLICT")
        requested = "xdist"
        if arg.startswith("--dist"):
            if value != "load":
                raise ValueError("E_CODEX_PARALLEL_DIST_REQUIRES_LOAD")
        elif value not in ("auto", "logical"):
            if not value.isdecimal() or int(value) < 1:
                raise ValueError("E_CODEX_PARALLEL_WORKER_COUNT")
            workers = int(value)
    return requested, workers, remaining


def dispatch_parallel(task, batch_ref, selectors, extra, helper, path, signature):
    data, scope, conflicts, decisions = parse_intent(path, task, batch_ref)
    requested, max_workers, collect_args = scheduler_options(data.get("method", "auto"), extra)
    if requested == "xdist" and importlib.util.find_spec("xdist") is None:
        raise ValueError("E_CODEX_XDIST_UNAVAILABLE")
    conflict_keys = [conflict_key(conflict) for conflict in conflicts]
    intent_hash = digest([scope.task_ref, batch_ref, sorted(scope.nodes), data["instruction_ref"], requested, sorted(conflict_keys)])
    with transaction(task) as state:
        existing = state["batches"].get(batch_ref)
    if existing is None:
        manifest = collect_manifest(task, batch_ref, selectors, collect_args, helper)
        if set(manifest["nodes"]) != scope.nodes:
            raise ValueError("E_CODEX_PARALLEL_NODE_SCOPE")
        if requested == "xdist" and not manifest["xdist"]:
            raise ValueError("E_CODEX_XDIST_UNAVAILABLE")
        method = "independent" if requested == "independent" or not manifest["xdist"] else "xdist"
        fresh = dict(signature=signature, project=str(Path.cwd()), mode="parallel", selected=selectors,
                     started_at=datetime.now(timezone.utc).isoformat(),
                     evidence_root=manifest["evidence_root"], owners=dict(zip(manifest["nodes"], manifest["owners"])),
                     nodes=manifest["nodes"], runs=[], groups={}, status="pending", method=method, max_workers=max_workers,
                     instruction_ref=data["instruction_ref"], task_ref=str(task), intent_hash=intent_hash,
                     r2_nodes=manifest["r2_nodes"], serial_constraints=manifest["serial_constraints"], accepted_conflicts={})
    show_constraints = True
    while True:
        with transaction(task) as state:
            if batch_ref not in state["batches"]:
                state["batches"][batch_ref] = fresh
                from ui_test_core.formal_catalog import begin_batch
                from ui_test_core.artifact_layout import dispatch_task_ref
                begin_batch(dispatch_task_ref(task), batch_ref, manifest, fresh["started_at"])
            batch = state["batches"][batch_ref]
            if batch.get("intent_hash") != intent_hash or batch["signature"] != signature:
                raise ValueError("E_CODEX_BATCH_INPUT_CHANGED")
            if state["active"] not in (None, batch_ref):
                previous = active_status(task, state)
                if state["active"] is not None:
                    print(f"active batch {state['active']}: {previous or 'pending previous batch'}")
                    return PAUSED
            reason = None
            if state["active"] == batch_ref or batch["status"] == "passed":
                state["active"] = batch_ref
                reason = reconcile_groups(task, state, batch_ref, resume_same_batch=True)
            if reason:
                if "running" not in reason:
                    report_interruption(task, batch_ref, batch, reason)
                print(f"active batch {state['active']}: {reason}")
                return PAUSED
            if batch["status"] in ("passed", "failed"):
                from ui_test_core.stage_delivery import publish_batch
                delivery = publish_batch(task, batch_ref, batch)
                batch.pop("interruption_report", None)
                print(f"UI-Test stage report: {delivery['report_url']}")
                return 0 if batch["status"] == "passed" else 1
            if show_constraints:
                for decision in batch["serial_constraints"]:
                    affected = [n for n in batch["nodes"] if n in (decision.get("node_ids") or batch["nodes"])]
                    if len(affected) > 1:
                        print(json.dumps(dict(serial_constraint=decision, affected_nodes=affected), ensure_ascii=False), flush=True)
                show_constraints = False
            held = held_nodes(batch, scope, conflicts, decisions)
            ready = select_wave(batch, held, conflicts)
            if not ready:
                unknown = [row["node_id"] for row in batch["runs"] if row["disposition"] == "unknown"]
                if unknown:
                    report_interruption(task, batch_ref, batch, "terminal-or-receipt-unconfirmed")
                    print(json.dumps(dict(unknown_nodes=unknown, pending_conflicts=batch["pending_conflicts"]), ensure_ascii=False))
                    return PAUSED
                batch["status"] = "awaiting-conflict-decision"
                state["active"] = None
                print(json.dumps(dict(pending_conflicts=batch["pending_conflicts"]), ensure_ascii=False))
                return PAUSED
            state["active"], batch["status"] = batch_ref, "running"
            groups = reserve_groups(task, batch, ready)
        observers = []
        for identity in groups:
            command = [sys.executable, str(ENTRY), "_observe-group", str(task), batch_ref, identity, helper or "", *extra]
            with (run_directory(task, identity) / "pytest.log").open("w", encoding="utf-8") as log:
                observers.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT))
        for observer in observers:
            observer.wait()
