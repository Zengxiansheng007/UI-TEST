"""The batch report must retain every authorized attempt bound to its source session."""
import json
from pathlib import Path

import pytest
from scripts.ui_test_core import stage_delivery


def test_distinct_sessions_same_node_are_distinct_attempts(tmp_path, monkeypatch):
    rows = [{"node_id": "test_case", "run_id": run, "session_ref": session, "session_hash": session}
            for session, run in [("s1", "first"), ("s2", "second")]]
    archives = {row["session_ref"]: [dict(case_id="A", node_id="test_case", run_id=row["run_id"],
                session_id=row["session_ref"], attempt_ref="attempts/" + row["run_id"],
                status=status, steps=[])] for row, status in zip(rows, ["failed", "passed"])}
    monkeypatch.setattr(stage_delivery, "formal_cases", lambda source, **kwargs: archives[source])
    batch = dict(nodes=["test_case"], runs=rows)
    publish = lambda: stage_delivery.publish_batch(tmp_path / "task", "batch", batch)
    delivery = publish()
    summary = json.loads(Path(delivery["execution_summary"]).read_text(encoding="utf8"))
    assert [(case["run_id"], case["status"]) for case in summary["cases"]] == [("first", "failed"), ("second", "passed")]
    archive_html = Path(delivery["report_html"]).read_bytes()
    batch["runs"] = [rows[0], rows[0]]
    with pytest.raises(ValueError):
        publish()
    assert Path(delivery["report_html"]).read_bytes() == archive_html
