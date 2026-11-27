"""A published failed batch with two sealed sessions remains independently readable."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.ui_test_core.artifact_layout import ProjectLayout, batch_stage_id, dispatch_task_ref
from scripts.ui_test_core.case_contracts import canonical_hash


def test_batch_reader_requires_all_original_sessions(tmp_path):
    skills = Path(__file__).resolve().parents[2]
    main = tmp_path / "suite/ui-test"
    for resource in ("scripts", "schemas", "references"):
        shutil.copytree(skills / "ui-test" / resource, main / resource, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(skills / "execution-report", main.parent / "report", ignore=shutil.ignore_patterns("__pycache__"))
    (main / "references/suite-layout.json").write_text(json.dumps({"execution-report": str(main.parent / "report")}))
    root = tmp_path / "project"
    root.mkdir()
    (root / "ui-test.project.yaml").touch()
    task, batch = root / "dispatch.json", "batch"
    stage_id = batch_stage_id(dispatch_task_ref(task), batch)
    stage = ProjectLayout(root).run_dir("playwright", stage_id)
    evidence = stage / "evidence"
    (evidence / "sessions").mkdir(parents=True)
    runs, owners = [], []
    for node in ("first", "second"):
        session_id = "SESSION-" + node
        session = dict(schema_version="ui-test.pytest-session-result.v2", session_id=session_id,
                       batch_id=batch, expected_nodes=[node], execution_origin="cli",
                       origin_evidence_digest="sha256:" + "1" * 64, all_required_nodes_committed=False,
                       pytest_exitstatus=1, session_status="failed", recorded_at="2026-11-27T00:00:00Z",
                       nodes=[dict(node_id=node, finalization_status="missing", disposition="not_executed",
                                   missing_reason="stopped before execution")])
        digest = canonical_hash(session)
        source = evidence / "sessions" / (session_id + ".json")
        source.write_text(json.dumps(dict(session, session_result_hash=digest)))
        runs.append(dict(node_id=node, run_id="reserved-" + node, session_ref=str(source), session_hash=digest,
                         disposition="not_executed"))
        owners.append(dict(case_id=node, branch_id=node, attempts=[], status="not_executed"))
    record = dict(stage_id=stage_id, stage_type="playwright", status="failed", origin={"kind": "unknown"}, cases=owners)
    (stage / "stage.json").write_text(json.dumps(record))
    journal = dict(active=None, batches={batch: dict(status="failed", evidence_root=str(evidence),
                                                     nodes=["first", "second"], runs=runs)})
    task.write_text(json.dumps(journal))
    output = tmp_path / "delivery"
    command = [sys.executable, str(main / "scripts/ui_test_suite.py"), "--suite", str(main), "execution-report",
               "--task-ref", str(task), "--batch-ref", batch, "--output"]
    subprocess.run([*command, str(output)], check=True, capture_output=True)
    result = json.loads((output / "execution-summary.json").read_bytes())
    assert result["run_id"] == stage_id and [c["node_id"] for c in result["cases"]] == ["first", "second"]
    runs[1]["session_hash"] = "sha256:" + "0" * 64
    task.write_text(json.dumps(journal))
    rejected = tmp_path / "rejected"
    failure = subprocess.run([*command, str(rejected)], capture_output=True)
    assert failure.returncode == 2 and b"E_STAGE_SESSION_IDENTITY" in failure.stderr
    assert not rejected.exists()
