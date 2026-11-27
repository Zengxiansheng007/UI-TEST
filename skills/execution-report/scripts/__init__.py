"""Public report interface for stage producers and read-only offline rebuilds."""
from pathlib import Path
from .generate_report import scan_sensitive
from .observations import observation_cases
from .stage_report import publish_stage_report
from ui_test_core.strict_json import load_strict_json


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
