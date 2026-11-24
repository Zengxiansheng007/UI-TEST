"""Bridge finalized Midscene fixture observations into the shared Python publisher."""
import json
import re
import sys
from pathlib import Path

REPORT_SCRIPTS = Path(__file__).resolve().parents[2] / "ui-test-execution-report" / "scripts"
sys.path.insert(0, str(REPORT_SCRIPTS))
from generate_report import scan_sensitive
from image_viewer import resolve_image_source
from stage_report import check_image_identity, publish_stage_report, step_images


def verify_capture(image, owner, output):
    if not image.get("path") and not image.get("data_uri") and image.get("missing_reason"):
        return
    capture_id = image.get("capture_id", "")
    if (not isinstance(capture_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", capture_id)
            or not re.fullmatch(r"[0-9a-f]{64}", str(image.get("sha256", "")))):
        raise ValueError("E_EXPLORATION_IMAGE_RECEIPT")
    receipt_path = (output / "images" / (capture_id + ".json")).resolve()
    if not receipt_path.is_relative_to(output.resolve()):
        raise ValueError("E_EXPLORATION_IMAGE_RECEIPT")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        raise ValueError("E_EXPLORATION_IMAGE_RECEIPT") from None
    expected = {**owner, "sha256": image["sha256"]}
    if any(image.get(k) != v or receipt.get(k) != v for k, v in expected.items()):
        raise ValueError("E_EXPLORATION_IMAGE_IDENTITY")
    if image.get("path"):
        if (image.get("data_uri") or Path(image["path"]).resolve() != Path(receipt["path"]).resolve()
                or not Path(image["path"]).resolve().is_relative_to(output.resolve())):
            raise ValueError("E_EXPLORATION_IMAGE_SOURCE")
    _, reason = resolve_image_source(image)
    if image.get("data_uri") and reason:
        raise ValueError("E_EXPLORATION_IMAGE_SOURCE")


def deliver(batch, output, *, archived=False):
    run_id = batch["run_id"]
    cases = batch["cases"]
    if (batch["stage"] != "midscene" or run_id != output.name or not cases
            or any(case["run_id"] != run_id for case in cases)):
        raise ValueError("E_EXPLORATION_BATCH_IDENTITY")
    if scan_sensitive(batch):
        raise ValueError("E_STAGE_SENSITIVE_FIELDS")
    source = output / "observations.json"
    identities = set()
    for case in cases:
        identity = (case["case_id"], case["attempt_ref"])
        if not all(isinstance(v, str) and v for v in identity) or identity in identities:
            raise ValueError("E_EXPLORATION_ATTEMPT_IDENTITY")
        identities.add(identity)
        for step in case["steps"]:
            check_image_identity("midscene", case, step)
            owner = dict(stage="midscene", run_id=run_id, case_id=case["case_id"],
                         attempt_ref=case["attempt_ref"], step_id=step.get("step_id"))
            for image in step_images(step):
                verify_capture(image, owner, output)
    if not archived:
        # Reserve the original observation before delivery. A failed renderer can retry this archive.
        with source.open("x", encoding="utf8") as stream:
            json.dump(batch, stream, ensure_ascii=False, indent=2)
    cases = [project_case(case) for case in cases]
    for case in cases:
        case["evidence_index"] = {"source": str(source), "case_id": case["case_id"]}
    delivery = publish_stage_report("midscene", run_id, cases, output)
    if cases[0].get("native_replay_url"):
        delivery["native_replay_url"] = cases[0]["native_replay_url"]
    return dict(delivery, observations=str(source))


def project_case(case):
    """Only an explicit stop boundary or an unstarted case proves an unexecuted plan item."""
    steps = list(case["steps"])
    recorded = {step.get("step_id") for step in steps}
    beyond_stop = case["status"] in {"not-executed", "not_executed"}
    for step in case.get("planned_steps", []):
        beyond_stop |= step["step_id"] == case.get("stopped_before")
        if step["step_id"] in recorded:
            if beyond_stop:
                raise ValueError("E_EXPLORATION_PLAN_CONFLICT")
            continue
        steps.append(dict(step_id=step["step_id"], action=step["action"],
                          expected_result=step.get("expected_result"), recorded=False,
                          status="not_executed" if beyond_stop else "unknown",
                          reason=case.get("reason") if beyond_stop else "本次观察未记录该步骤"))
    return {**case, "steps": steps}


if __name__ == "__main__":
    if sys.argv[1] == "--archive":
        source = Path(sys.argv[2]).resolve(strict=True)
        if source.name != "observations.json":
            raise ValueError("E_EXPLORATION_ARCHIVE")
        print(json.dumps(deliver(json.loads(source.read_text(encoding="utf8")), source.parent, archived=True)))
    else:
        print(json.dumps(deliver(json.load(sys.stdin), Path(sys.argv[1]).resolve())))
