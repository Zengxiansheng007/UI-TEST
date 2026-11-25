"""Resolve explicit project-local stage lineage before a formal run starts."""
import os
from pathlib import Path

from .artifact_layout import ProjectLayout
from .codex_dispatch_state import read
from .path_planner import validate_existing_path_containment


def capture_origin(project):
    upstream = os.environ.get("UI_TEST_EXPLORATION_RUN_ID")
    mode = os.environ.get("UI_TEST_STAGE_ORIGIN")
    if mode not in (None, "", "independent") or (mode and upstream):
        raise ValueError("E_STAGE_ORIGIN_CONFLICT")
    if not upstream:
        return {"kind": "independent" if mode else "unknown"}
    folder = project.run_dir("midscene", upstream)
    files = {name: folder / name for name in ("observations.json", "report.html", "execution-summary.json")}
    for path in files.values():
        validate_existing_path_containment(project.root, path)
        if not path.is_file():
            raise ValueError("E_STAGE_ORIGIN_MISSING")
    for name in ("observations.json", "execution-summary.json"):
        data = read(files[name])
        if (data.get("stage"), data.get("run_id")) != ("midscene", upstream):
            raise ValueError("E_STAGE_ORIGIN_IDENTITY")
    return dict(kind="exploration", stage_id=upstream, report=files["report.html"].relative_to(project.root).as_posix(),
                observations=files["observations.json"].relative_to(project.root).as_posix())


def recorded_origin(folder, stage, stage_id):
    start = Path(folder) / "start.json"
    if not start.is_file():
        return {"kind": "unknown"}
    validate_existing_path_containment(start.parent, start)
    record = read(start)
    if (record["stage_type"],record["stage_id"]) != (stage,stage_id):
        raise ValueError("E_STAGE_ORIGIN_IDENTITY")
    return record.get("origin", {"kind": "unknown"})
