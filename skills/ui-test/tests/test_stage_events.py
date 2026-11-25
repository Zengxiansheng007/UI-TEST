"""Original registration facts survive unavailable SQLite and a process interruption."""
import sqlite3
from contextlib import closing

from scripts.ui_test_core.run_catalog import refresh_catalog
from scripts.ui_test_core.stage_events import stage_started, record_attempt


def test_replay_locked_index_retry_and_missing_evidence(tmp_path):
    owners = [dict(case_id=case, branch_id="main") for case in ("A", "B")]
    args = (tmp_path, "midscene", "interrupted")
    stage_started(*args, "2026-11-25T10:00:00+08:00", owners)
    database = tmp_path / "runs.sqlite3"
    with closing(sqlite3.connect(database)) as db:
        assert db.execute("select count(*) from cases").fetchone() == (2,)
    database.rename(tmp_path / "previous.sqlite3")
    database.mkdir()  # Substitute an unwritable database target after the first checkpoint.
    for attempt, status in [("first", "blocked"), ("retry", "observed")]:
        error = record_attempt(*args, owners[0], dict(attempt_ref=attempt, status=status,
                               execution_ref="original.json", evidence_ref="missing.json"))
        assert error == "OperationalError"
    database.rmdir()
    refresh_catalog(tmp_path)
    refresh_catalog(tmp_path)
    with sqlite3.connect(database) as db:
        assert db.execute("select case_id, attempt_ref, status from run_attempts order by case_id,attempt_order").fetchall() == [
            ("A", "first", "blocked"), ("A", "retry", "observed"), ("B", None, "not_executed")]
        assert db.execute("select stage_status,ended_at from stages").fetchone() == ("running", None)
    assert "缺件" in (tmp_path / "index.html").read_text("utf8")
