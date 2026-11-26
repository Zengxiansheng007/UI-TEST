"""Translate sealed business records into the project-relative catalog contract."""
import sqlite3
from pathlib import Path

from .run_catalog import register_stage


def catalog_delivery(root, stage_id, stage_type, cases, delivery, *, started_at, ended_at, status):
    root = Path(root).resolve()

    def relative(path):
        return Path(path).resolve().relative_to(root).as_posix() if path else None

    grouped = {}
    for row in cases:
        case_id = row.get("case_id") or row["node_id"]
        branch = row.get("branch_id") or row.get("node_id") or case_id
        owner = grouped.setdefault((case_id, branch), dict(case_id=case_id, branch_id=branch, attempts=[]))
        owner["status"] = row["status"]
        if row["status"] in {"not-executed", "not_executed"} and not row.get("run_result"):
            continue  # A reservation is not an actual attempt.
        identity = row.get("attempt_ref") or row.get("run_id")
        if identity:
            owner["attempts"].append(dict(attempt_ref=identity, status=row["status"], version=row.get("version"),
                                          binding=row.get("binding"), execution_ref=relative(row.get("execution_source")),
                                          evidence_ref=relative(row.get("evidence_source"))))
    record = dict(stage_id=stage_id, stage_type=stage_type, started_at=started_at, ended_at=ended_at,
                  status=status, report_ref=relative(delivery["report_html"]), cases=list(grouped.values()))
    if stage_type == "playwright":
        from ui_test_core.stage_origin import recorded_origin
        record["origin"] = recorded_origin(Path(delivery["report_html"]).parent, stage_type, stage_id)
    try:
        register_stage(root, record)
    except (sqlite3.Error, OSError) as exc:
        delivery["catalog_error"] = type(exc).__name__  # Sealed business results remain independently available.
    return delivery
