"""Persist producer milestones first; derive the disposable catalog from their originals."""
import sqlite3
import time

from ui_test_core.artifact_layout import ProjectLayout
from ui_test_core.codex_dispatch_state import publish, read
from ui_test_core.file_lock import exclusive_file_lock
from ui_test_core.path_planner import validate_existing_path_containment
from ui_test_core.path_utils import short_id


def update_index(root):
    from .run_catalog import refresh_catalog
    try:
        refresh_catalog(root)
    except (sqlite3.Error, OSError) as exc:
        return type(exc).__name__  # Next refresh reads the saved fact without re-running the case.


def stage_started(root, stage, stage_id, started_at, owners):
    folder = ProjectLayout(root).reserve_run(stage, stage_id)
    target = folder / "start.json"
    validate_existing_path_containment(root, target)
    guard = folder / ".events.lock"
    validate_existing_path_containment(root, guard)
    with exclusive_file_lock(guard):
        if not target.exists():
            distinct = dict.fromkeys((row["case_id"], row["branch_id"]) for row in owners)
            from ui_test_core.stage_origin import capture_origin
            origin = capture_origin(ProjectLayout(root)) if stage == "playwright" else {}
            publish(target, dict(stage_type=stage, stage_id=stage_id, origin=origin, started_at=started_at, status="running",
                                 cases=[dict(case_id=c, branch_id=b, status="not_executed", attempts=[])
                                        for c, b in distinct]))
    return update_index(root)


def record_attempt(root, stage, stage_id, owner, attempt, *, observation=None):
    folder = ProjectLayout(root).run_dir(stage, stage_id)
    identity = (owner["case_id"], owner["branch_id"], attempt["attempt_ref"])
    target = folder / "events" / (short_id(*identity) + ".json")
    guard = folder / ".events.lock"
    for path in (target, guard):
        validate_existing_path_containment(root, path)
    with exclusive_file_lock(guard):
        target.parent.mkdir(exist_ok=True)
        old = read(target) if target.exists() else None
        if old and list(identity) != old["identity"]:
            raise ValueError("E_STAGE_ATTEMPT_COLLISION")
        if not old or old["attempt"]["status"] == "running" or attempt["status"] != "running":
            record = dict(identity=list(identity), order=old["order"] if old else time.time_ns(), attempt=attempt)
            if observation is not None:
                ref = target.relative_to(root).as_posix()
                record.update(observation=observation, attempt=dict(attempt, execution_ref=ref, evidence_ref=ref))
            publish(target, record)
    return update_index(root)


def replay_stage(root, folder, *, archived_files=None):
    archived_files = archived_files or {}
    sealed = folder / "stage.json"
    source = sealed if sealed.is_file() or sealed in archived_files else folder / "start.json"
    validate_existing_path_containment(root, source)
    stage = read(archived_files.get(source,source))
    if not (folder / "start.json").is_file() and folder/"start.json" not in archived_files:
        return stage  # Legacy stages had one sealed record.
    cases = {(c["case_id"], c["branch_id"]): c for c in stage["cases"]}
    sealed_attempts = {(c,b): {a["attempt_ref"]: a for a in row["attempts"]} for (c,b), row in cases.items()}
    for case in cases.values():
        case["attempts"] = []
    events = []
    paths = set((folder/"events").glob("*.json"))
    paths.update(path for path in archived_files if path.parent == folder/"events" and path.suffix==".json")
    for path in paths:
        validate_existing_path_containment(root, path)
        event = read(archived_files.get(path,path))
        if path.name != short_id(*event["identity"]) + ".json":
            raise ValueError("E_STAGE_ATTEMPT_IDENTITY")
        events.append(event)
    for event in sorted(events, key=lambda e: (e["order"], e["identity"])):
        c, b, ref = event["identity"]
        case = cases.setdefault((c, b), dict(case_id=c, branch_id=b, attempts=[], status="unknown"))
        attempt = event["attempt"]
        if ref != attempt["attempt_ref"]:
            raise ValueError("E_STAGE_ATTEMPT_IDENTITY")
        authoritative = sealed_attempts.get((c,b), {}).pop(ref, None)
        if authoritative is None and stage["stage_type"] == "playwright" and attempt["status"] == "running":
            from .formal_catalog import recover_terminal
            attempt = recover_terminal(root, c, b, attempt)
        case["attempts"].append(authoritative or attempt)
        if source != sealed:
            case["status"] = attempt["status"]
    for key, pending in sealed_attempts.items():
        cases[key]["attempts"].extend(pending.values())
    stage["cases"] = list(cases.values())
    return stage
