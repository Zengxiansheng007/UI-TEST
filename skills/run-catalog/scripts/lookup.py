"""Find the original records and version-bound artifacts for a project run."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from ui_test_core.artifact_layout import ProjectLayout
from .run_catalog import checked_ref, refresh_catalog


def lookup(project, *, stage=None, case=None, branch=None, attempt=None, original=None):
    root = Path(project).resolve()
    layout = ProjectLayout(root)
    missing = set()
    if original:
        path = Path(original)
        path = path if path.is_absolute() else root / path
        relative = path.resolve().relative_to(root).as_posix()
        checked_ref(root, relative)
        if not path.is_file():
            return dict(status="missing", matches=[], missing=[relative])
        if path.name not in {"stage.json", "start.json"}:
            raise ValueError("E_CATALOG_EXPECTED_STAGE_ORIGINAL")
        identity = json.loads(path.read_text(encoding="utf8"))
        folder = layout.run_dir(identity["stage_type"], identity["stage_id"])
        if path.resolve().parent != folder or (stage is not None and identity["stage_id"] != stage):
            raise ValueError("E_CATALOG_STAGE_IDENTITY")
        stage = identity["stage_id"]
    refresh_catalog(root)
    sql = """SELECT * FROM run_attempts LEFT JOIN version_bindings
             USING(stage_id,case_id,branch_id,attempt_ref)"""
    filters = {key: value for key, value in (("stage_id", stage), ("case_id", case),
               ("branch_id", branch), ("attempt_ref", attempt)) if value is not None}
    if filters:
        sql += " WHERE " + " AND ".join(key + "=?" for key in filters)
    matches = {}

    def require(ref, label, digest=None):
        if not ref:
            missing.add(label)
            return
        target = root / checked_ref(root, ref)
        if not target.is_file():
            missing.add(ref)
        elif digest and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            missing.add(ref + " (sha256 mismatch)")

    with closing(sqlite3.connect((root / "runs.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute(sql + " ORDER BY stage_id,case_id,branch_id,attempt_order", tuple(filters.values())):
            sid = row["stage_id"]
            if sid not in matches:
                folder = layout.run_dir(row["stage_type"], sid)
                filename = "stage.json" if (folder / "stage.json").exists() else "start.json"
                source = (folder / filename).relative_to(root).as_posix()
                require(source, "stage original")
                require(row["report_ref"], sid + ": report_ref")
                matches[sid] = dict(stage_id=sid, stage_type=row["stage_type"], original=source,
                                    report_ref=row["report_ref"], attempts=[])
            fields = ("case_id","branch_id","case_status","attempt_ref","status","version","entry","node_id",
                      "execution_ref","evidence_ref","sha256")
            item = {key: row[key] for key in fields}
            item["dependencies"] = json.loads(row["dependencies"] or "[]")
            if row["attempt_ref"] is not None:
                key = "/".join(str(row[k]) for k in ("stage_id","case_id","branch_id","attempt_ref"))
                require(row["entry"], key + ": version binding", row["sha256"])
                for dep in item["dependencies"]:
                    require(dep["entry"], key + ": dependency", dep["sha256"])
                for field in ("execution_ref", "evidence_ref"):
                    if row[field]:
                        require(row[field], key + ": " + field)
            matches[sid]["attempts"].append(item)
    status = "not_found"
    if matches:
        status = "ambiguous" if len(matches) > 1 else ("missing" if missing else "found")
    return dict(status=status, matches=list(matches.values()), missing=sorted(missing))
