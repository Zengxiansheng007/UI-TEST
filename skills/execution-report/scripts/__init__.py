"""Public report interface for stage producers and read-only offline rebuilds."""
from pathlib import Path
from .generate_report import scan_sensitive
from .observations import observation_cases
from .stage_report import publish_stage_report
from ui_test_core.strict_json import load_strict_json


def rebuild_batch(task, batch_id, destination):
    """Read a terminal dispatch journal without reserving runs or invoking its controller."""
    from ui_test_core.stage_delivery import batch_location, formal_batch_cases
    task = Path(task).resolve(strict=True)
    journal = load_strict_json(task)
    batch = journal["batches"].get(batch_id)
    if (not batch or journal.get("active") == batch_id or batch["status"] not in {"passed", "failed"}
            or not batch.get("runs")):
        raise ValueError("E_STAGE_BATCH_NOT_SEALED")
    destination = Path(destination).resolve()
    evidence = Path(batch["evidence_root"]).resolve(strict=True)
    if any(Path(row["session_ref"]).resolve().parent != evidence / "sessions" for row in batch["runs"]):
        raise ValueError("E_STAGE_BATCH_SESSION_ROOT")
    project, stage_id = batch_location(task, batch_id, batch)
    original = project.run_dir("playwright", stage_id)
    if any(destination.is_relative_to(root) for root in (project.root, evidence, task.parent)):
        raise ValueError("E_STAGE_OUTPUT_OVERLAPS_ORIGINAL: " + str(destination))
    record = load_strict_json(original / "stage.json")
    if (record["stage_type"], record["stage_id"], record["status"]) != ("playwright", stage_id, batch["status"]):
        raise ValueError("E_STAGE_BATCH_IDENTITY")
    cases = formal_batch_cases(batch_id, batch)
    # The published stage independently binds every selected case and its original attempts.
    attempts = {}
    for case in cases:
        case_id = case.get("case_id") or case["node_id"]
        branch = case.get("branch_id") or case.get("node_id") or case_id
        refs = attempts.setdefault((case_id, branch), [])
        identity = case.get("attempt_ref") or case.get("run_id")
        if identity and (case["status"] not in {"not-executed", "not_executed"} or case.get("run_result")):
            refs.append((identity, case["status"]))
    expected = [((case["case_id"], case["branch_id"]), [(a["attempt_ref"], a["status"]) for a in case["attempts"]])
                for case in record["cases"]]
    if list(attempts.items()) != expected:
        raise ValueError("E_STAGE_BATCH_IDENTITY")
    destination.mkdir(parents=True, exist_ok=False)
    return publish_stage_report("playwright", stage_id, cases, destination, origin=record["origin"],
                                source_root=project.root, original_folder=original)


def rebuild(observations, session, destination):
    if (observations is None) == (session is None):
        raise ValueError("E_STAGE_SELECT_ONE_SOURCE")
    source = Path(observations or session).resolve(strict=True)
    destination = Path(destination).resolve()
    if observations is not None:
        if source.name != "observations.json":
            raise ValueError("E_EXPLORATION_ARCHIVE: expected observations.json")
        batch = load_strict_json(source)
        cases = observation_cases(batch, source.parent)
        stage, run_id, evidence_root = "midscene", batch["run_id"], source.parent
    else:
        from ui_test_core.stage_delivery import formal_cases
        cases = formal_cases(source)
        stage, run_id, evidence_root = "playwright", source.stem, source.parent.parent
    if destination.is_relative_to(evidence_root):
        raise ValueError("E_STAGE_OUTPUT_OVERLAPS_ORIGINAL: " + str(destination))
    destination.mkdir(parents=True, exist_ok=False)
    return publish_stage_report(stage, run_id, cases, destination, source_root=evidence_root)
