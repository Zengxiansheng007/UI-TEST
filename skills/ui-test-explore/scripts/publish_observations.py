"""Bridge finalized Midscene fixture observations into the shared Python publisher."""
from collections import Counter
import json
import re
import sys
from pathlib import Path

REPORT_SCRIPTS = Path(__file__).resolve().parents[2] / "ui-test-execution-report" / "scripts"
sys.path.insert(0, str(REPORT_SCRIPTS))
sys.path.insert(0, str(REPORT_SCRIPTS.parents[1] / "ui-test" / "scripts"))
from ui_test_core.artifact_layout import ProjectLayout, short_id
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
    if receipt.get("branch_id") != image.get("branch_id") or any(
            image.get(k) != v or receipt.get(k) != v for k, v in expected.items()):
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
    if (batch["stage"] != "midscene" or output.name not in (run_id, "m" + short_id(run_id)) or not cases
            or any(case["run_id"] != run_id for case in cases)):
        raise ValueError("E_EXPLORATION_BATCH_IDENTITY")
    if scan_sensitive(batch):
        raise ValueError("E_STAGE_SENSITIVE_FIELDS")
    source = output / "observations.json"
    identities = set()
    legacy_owners = Counter((case["case_id"], case["attempt_ref"]) for case in cases)
    for case in cases:
        identity = (case["case_id"], case.get("branch_id", case["case_id"]), case["attempt_ref"])
        if not all(isinstance(v, str) and v for v in identity) or identity in identities:
            raise ValueError("E_EXPLORATION_ATTEMPT_IDENTITY")
        identities.add(identity)
        for step in case["steps"]:
            check_image_identity("midscene", case, step)
            owner = dict(stage="midscene", run_id=run_id, case_id=case["case_id"],
                         attempt_ref=case["attempt_ref"], step_id=step.get("step_id"))
            for image in step_images(step):
                # Older captures omitted the branch. Their case/attempt must have a single owner.
                expected = dict(owner)
                if "branch_id" in image or legacy_owners[case["case_id"], case["attempt_ref"]] > 1:
                    expected["branch_id"] = identity[1]
                verify_capture(image, expected, output)
    if not archived:
        # Reserve the original observation before delivery. A failed renderer can retry this archive.
        with source.open("x", encoding="utf8") as stream:
            json.dump(batch, stream, ensure_ascii=False, indent=2)
    cases = [project_case(case) for case in cases]
    for case in cases:
        case.update(execution_source=str(source), evidence_source=str(source))
        case["evidence_index"] = {"source": str(source), "case_id": case["case_id"],
                                  "branch_id": case.get("branch_id", case["case_id"]), "attempt_ref": case["attempt_ref"]}
    delivery = publish_stage_report("midscene", run_id, cases, output)
    if output.parent.name == "运行":
        from ui_test_core.catalog_delivery import catalog_delivery
        status = "blocked" if any(case["status"] == "blocked" for case in cases) else "observed"
        catalog_delivery(output.parent.parent, run_id, "midscene", cases, delivery,
                         started_at=batch.get("started_at"), ended_at=batch.get("ended_at"), status=status)
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
    if sys.argv[1] == "--bind-plan":
        from ui_test_core.execution_version import bind_exploration
        print(json.dumps(bind_exploration(sys.argv[2], json.load(sys.stdin))))
    elif sys.argv[1] == "--event":
        from ui_test_core.stage_events import stage_started, record_attempt

        output = Path(sys.argv[2]).resolve()
        root = output.parent.parent
        run_id, event = sys.argv[3:5]
        data = json.load(sys.stdin)
        if ProjectLayout(root).run_dir("midscene", run_id) != output or scan_sensitive(data):
            raise ValueError("E_EXPLORATION_CHECKPOINT")
        if event == "start":
            result = stage_started(root, "midscene", run_id, data["started_at"], data["owners"])
        elif event == "attempt":
            attempt = {k: data[k] for k in ("attempt_ref", "status", "version", "binding") if k in data}
            result = record_attempt(root, "midscene", run_id, data, attempt, observation=data)
        else:
            raise ValueError("E_EXPLORATION_EVENT")
        print(json.dumps(result))
    elif sys.argv[1] == "--reserve":
        try:
            reserved = ProjectLayout(sys.argv[2]).reserve_run("midscene", sys.argv[3], exclusive=True)
        except FileExistsError:
            reserved = None
        print(json.dumps(str(reserved) if reserved else None))
    elif sys.argv[1] == "--allocate":
        print(json.dumps(str(ProjectLayout(sys.argv[2]).run_dir("midscene", sys.argv[3]))))
    elif sys.argv[1] == "--archive":
        source = Path(sys.argv[2]).resolve(strict=True)
        if source.name != "observations.json":
            raise ValueError("E_EXPLORATION_ARCHIVE")
        print(json.dumps(deliver(json.loads(source.read_text(encoding="utf8")), source.parent, archived=True)))
    else:
        print(json.dumps(deliver(json.load(sys.stdin), Path(sys.argv[1]).resolve())))
