"""Rebuild both project readers from durable stage records, without reading page evidence."""
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .artifact_layout import ProjectLayout
from .codex_dispatch_state import publish, read
from .file_lock import exclusive_file_lock
from .path_planner import validate_existing_path_containment
from .catalog_html import render_catalog

SCHEMA = """
CREATE TABLE IF NOT EXISTS stages(stage_id TEXT PRIMARY KEY, stage_type TEXT NOT NULL,
 started_at TEXT, ended_at TEXT, local_date TEXT, stage_status TEXT NOT NULL, report_ref TEXT);
CREATE TABLE IF NOT EXISTS cases(stage_id TEXT, case_id TEXT, branch_id TEXT, case_status TEXT NOT NULL,
 PRIMARY KEY(stage_id,case_id,branch_id));
CREATE TABLE IF NOT EXISTS attempts(stage_id TEXT, case_id TEXT, branch_id TEXT, attempt_ref TEXT,
 status TEXT NOT NULL, version TEXT, execution_ref TEXT, evidence_ref TEXT,
 PRIMARY KEY(stage_id,case_id,branch_id,attempt_ref));
CREATE TABLE IF NOT EXISTS version_bindings(stage_id TEXT, case_id TEXT, branch_id TEXT, attempt_ref TEXT,
 node_id TEXT NOT NULL, source TEXT NOT NULL, entry TEXT NOT NULL, sha256 TEXT NOT NULL,
 dependencies TEXT NOT NULL, release TEXT, PRIMARY KEY(stage_id,case_id,branch_id,attempt_ref));
CREATE TABLE IF NOT EXISTS stage_origins(stage_id TEXT PRIMARY KEY, exploration_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS current_scripts(case_id TEXT, branch_id TEXT, display_name TEXT, source TEXT,
 status TEXT, reason TEXT, entry TEXT, node_id TEXT, PRIMARY KEY(case_id,branch_id));
CREATE TABLE IF NOT EXISTS legacy_artifacts(path TEXT, source TEXT, kind TEXT, status TEXT, reason TEXT,
 case_id TEXT, branch_id TEXT, version TEXT);
CREATE TABLE IF NOT EXISTS archive_history(stage_id TEXT, manifest_sha256 TEXT PRIMARY KEY,
 archive_dir TEXT, disposition TEXT, media_status TEXT, restored_dir TEXT, reader TEXT, approval_id TEXT,
 recorded_at TEXT, stage_type TEXT, started_at TEXT, ended_at TEXT, local_date TEXT, stage_status TEXT);
CREATE TABLE IF NOT EXISTS archive_attempts(manifest_sha256 TEXT, case_id TEXT, branch_id TEXT,
 attempt_ref TEXT, status TEXT, version TEXT, execution_file TEXT, evidence_file TEXT, script_file TEXT);
CREATE VIEW IF NOT EXISTS archived_runs AS SELECT h.*, a.case_id,a.branch_id,a.attempt_ref,
 coalesce(a.status,h.stage_status) AS status,a.version,a.execution_file,a.evidence_file,a.script_file
 FROM archive_history h LEFT JOIN archive_attempts a USING(manifest_sha256);
CREATE VIEW IF NOT EXISTS run_attempts AS SELECT s.*, c.case_id,c.branch_id,c.case_status,
 a.rowid AS attempt_order,a.attempt_ref,coalesce(a.status,c.case_status,s.stage_status) AS status,a.version,a.execution_ref,a.evidence_ref
 FROM stages s LEFT JOIN cases c USING(stage_id) LEFT JOIN attempts a USING(stage_id,case_id,branch_id);
"""


def project_zone(root):
    settings = root / "catalog-settings.json"
    name = read(settings)["project_timezone"] if settings.exists() else "+08:00"
    if re.fullmatch(r"[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]", name):
        minutes = int(name[1:3]) * 60 + int(name[4:])
        return timezone(timedelta(minutes=minutes if name[0] == "+" else -minutes))
    return ZoneInfo(name)


def instant(value):
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.utcoffset() is None:
        raise ValueError("E_CATALOG_TIME_OFFSET")
    return dt


def checked_ref(root, ref):
    if ref is not None:
        if not ref or Path(ref).is_absolute() or any(p in {"..", "_private"} for p in Path(ref).parts) or ":" in ref:
            raise ValueError("E_CATALOG_PROJECT_REF")
        validate_existing_path_containment(root, root / ref)
    return ref


def insert_stage(db, root, stage, zone):
    stage_id = stage["stage_id"]
    started = instant(stage.get("started_at"))
    instant(stage.get("ended_at"))
    day = started.astimezone(zone).date().isoformat() if started else None
    db.execute("INSERT INTO stages VALUES(?,?,?,?,?,?,?)",
               (stage_id, stage["stage_type"], stage.get("started_at"), stage.get("ended_at"), day,
                stage["status"], checked_ref(root, stage.get("report_ref"))))
    for case in stage["cases"]:
        owner = (stage_id, case["case_id"], case["branch_id"])
        db.execute("INSERT INTO cases VALUES(?,?,?,?)", (*owner, case["status"]))
        for attempt in case["attempts"]:
            binding = attempt.get("binding")
            if binding:
                for dep in binding["dependencies"]:
                    checked_ref(root, dep["entry"])
                db.execute("INSERT INTO version_bindings VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (*owner, attempt["attempt_ref"], binding["node_id"], binding["source"],
                            checked_ref(root, binding["entry"]), binding["sha256"],
                            json.dumps(binding["dependencies"], ensure_ascii=False), binding.get("release")))
            db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?)",
                       (*owner, attempt["attempt_ref"], attempt["status"], attempt.get("version"),
                        checked_ref(root, attempt.get("execution_ref")), checked_ref(root, attempt.get("evidence_ref"))))


def render_database_catalog(root, db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='version_bindings' AND type='table'").fetchone():
        sql = """SELECT * FROM run_attempts LEFT JOIN version_bindings
                 USING(stage_id,case_id,branch_id,attempt_ref)"""
    else:
        sql = "SELECT *, NULL AS entry FROM run_attempts"  # Older indexes can be opened read-only.
    rows = list(db.execute(sql + " ORDER BY local_date DESC,stage_id,case_id,branch_id,attempt_order"))
    downstream = {}
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='stage_origins' AND type='table'").fetchone():
        for parent, child, report in db.execute("SELECT exploration_id,stage_id,report_ref FROM stage_origins JOIN stages USING(stage_id)"):
            downstream.setdefault(parent, []).append((child, report))
    current = []
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='current_scripts'").fetchone():
        current = list(db.execute("SELECT * FROM current_scripts ORDER BY display_name,case_id,branch_id"))
    archives = {}
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='archived_runs'").fetchone():
        for item in db.execute("SELECT * FROM archived_runs ORDER BY recorded_at DESC,manifest_sha256 DESC"):
            archives.setdefault(item["stage_id"], []).append(item)
    render_catalog(root, rows, db.execute("SELECT * FROM legacy_artifacts"), downstream, current, archives)


def insert_archive_history(db, root, zone):
    from .archive_history import catalog_archive, history_records
    stages = {}
    for record in history_records(root):
        stage = record["stage"]
        stages.setdefault(stage["stage_id"], stage)
        started = instant(stage["started_at"])
        day = started.astimezone(zone).date().isoformat() if started else None
        header, links = catalog_archive(root, record)
        db.execute("INSERT INTO archive_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (*header, stage["stage_type"], stage["started_at"], stage["ended_at"], day, stage["status"]))
        for case in stage["cases"]:
            for attempt in case["attempts"] or [{}]:
                key = (case["case_id"], case["branch_id"], attempt.get("attempt_ref"))
                db.execute("INSERT INTO archive_attempts VALUES(?,?,?,?,?,?,?,?,?)",
                           (record["manifest_sha256"], *key, attempt.get("status", case["status"]),
                            attempt.get("version"), *links.get(key, (None,None,None))))
    return stages


def refresh_catalog(root):
    root = Path(root).resolve()
    for name in ("runs.sqlite3","runs.sqlite3-journal","index.html",".catalog.lock","catalog-settings.json"):
        validate_existing_path_containment(root, root / name)
    zone = project_zone(root)
    with exclusive_file_lock(root / ".catalog.lock"), closing(sqlite3.connect(root / "runs.sqlite3")) as db:
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        with db:
            for table in ("attempts","cases","stages","legacy_artifacts","version_bindings","stage_origins","current_scripts",
                          "archive_history","archive_attempts"):
                db.execute("DELETE FROM " + table)
            from .stage_events import replay_stage
            archived = insert_archive_history(db, root, zone)
            layout = ProjectLayout(root)
            archived_folders = {layout.run_dir(s["stage_type"], sid) for sid,s in archived.items()}
            paths = {p.parent for name in ("start.json", "stage.json") for p in (root / "运行").glob("*/" + name)}
            stages = list(archived.values())
            for folder in sorted(paths - archived_folders):
                stage = replay_stage(root, folder)
                if folder != layout.run_dir(stage["stage_type"], stage["stage_id"]):
                    raise ValueError("E_CATALOG_STAGE_IDENTITY")
                stages.append(stage)
            for stage in stages:
                insert_stage(db, root, stage, zone)
                origin = stage.get("origin") or {}
                if stage["stage_type"] == "playwright" and origin.get("kind") == "exploration":
                    db.execute("INSERT INTO stage_origins VALUES(?,?)", (stage["stage_id"], origin["stage_id"]))
            if (root / "legacy-sources.json").is_file() or (root / "用例").is_dir():
                from .legacy_inventory import discover_legacy
                db.executemany("INSERT INTO legacy_artifacts VALUES(:path,:source,:kind,:status,:reason,:case_id,:branch_id,:version)",
                               discover_legacy(root))
            from .current_scripts import current_scripts
            db.executemany("INSERT INTO current_scripts VALUES(:case_id,:branch_id,:display_name,:source,:status,:reason,:entry,:node_id)",
                           current_scripts(root, db.execute("SELECT * FROM legacy_artifacts")))
        render_database_catalog(root, db)
    return root / "index.html"


def register_stage(root, record):
    layout = ProjectLayout(root)
    folder = layout.reserve_run(record["stage_type"], record["stage_id"])
    target = folder / "stage.json"
    validate_existing_path_containment(layout.root, target)
    publish(target, record)
    return refresh_catalog(layout.root)
