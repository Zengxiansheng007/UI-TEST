"""Publish validated Midscene observations through the selected report owner."""
import json
import sys
import os
import runpy
from pathlib import Path


def runtime():
    # Legacy commands use the source distribution layout when no installed suite is selected.
    configured = os.environ.get("UI_TEST_SUITE")
    default = Path(__file__).resolve().parents[2] / "ui-test"
    first = Path(configured.split(os.pathsep)[0]) if configured else default
    launcher = first / "scripts/ui_test_suite.py"
    if not launcher.is_file():
        raise ValueError("E_SUITE_MISSING: " + str(first))
    root = runpy.run_path(str(launcher))["activate"]()
    from ui_test_core.suite import selected_suite
    return selected_suite(root)

owner = runtime().load_package("execution-report")
from ui_test_core.artifact_layout import ProjectLayout
scan_sensitive = owner.scan_sensitive


def deliver(batch, output, *, archived=False):
    run_id = batch["run_id"]
    source = output / "observations.json"
    cases = owner.observation_cases(batch, output)
    if not archived:
        # Reserve the original observation before delivery. A failed renderer can retry this archive.
        with source.open("x", encoding="utf8") as stream:
            json.dump(batch, stream, ensure_ascii=False, indent=2)
    delivery = owner.publish_stage_report("midscene", run_id, cases, output)
    if output.parent.name == "运行":
        from ui_test_core.catalog_delivery import catalog_delivery
        status = "blocked" if any(case["status"] == "blocked" for case in cases) else "observed"
        catalog_delivery(output.parent.parent, run_id, "midscene", cases, delivery,
                         started_at=batch.get("started_at"), ended_at=batch.get("ended_at"), status=status)
    if cases[0].get("native_replay_url"):
        delivery["native_replay_url"] = cases[0]["native_replay_url"]
    return dict(delivery, observations=str(source))


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
