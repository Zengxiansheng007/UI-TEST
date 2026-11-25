"""Public catalog and SQL use the same case-scoped attempt identities."""
import sqlite3

from scripts.ui_test_core.run_catalog import register_stage, refresh_catalog


def test_cross_midnight_retries_and_unstarted_case(tmp_path):
    (tmp_path / "catalog-settings.json").write_text('{"project_timezone":"+08:00"}')
    record = dict(stage_id="batch", stage_type="playwright", started_at="2026-03-04T15:50:00Z",
                  ended_at="2026-03-04T16:10:00Z", status="passed", report_ref="stage/report.html",
                  cases=[dict(case_id=case, branch_id="main", status=status, attempts=[
                      dict(attempt_ref=str(i), status=s, version="v1", execution_ref=f"{case}{i}.json",
                           evidence_ref="index.json") for i, s in enumerate(statuses, 1)])
                         for case, status, statuses in [("A","passed",["failed","passed"]),
                                                        ("B","passed",["passed"]),("C","not_executed",[])]])
    register_stage(tmp_path, record)
    refresh_catalog(tmp_path)
    with sqlite3.connect(tmp_path / "runs.sqlite3") as db:
        assert db.execute("SELECT case_id,attempt_ref,status,local_date FROM run_attempts ORDER BY case_id,attempt_ref").fetchall() == [
            ("A","1","failed","2026-03-04"), ("A","2","passed","2026-03-04"),
            ("B","1","passed","2026-03-04"), ("C",None,"not_executed","2026-03-04")]
        assert db.execute("SELECT DISTINCT report_ref FROM run_attempts WHERE version='v1'").fetchall() == [("stage/report.html",)]
    html = (tmp_path / "index.html").read_text("utf8")
    assert "更新时间" in html and "A1.json" in html and "B1.json" in html


def test_one_project_run_id_can_only_be_reserved_for_one_stage_type(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from scripts.ui_test_core.artifact_layout import ProjectLayout

    start = Barrier(2)
    layout = ProjectLayout(tmp_path)
    def reserve(stage):
        start.wait()
        try:
            return layout.reserve_run(stage, "shared").is_dir()
        except ValueError as error:
            assert str(error) == "E_CATALOG_STAGE_ID_COLLISION"
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, ["midscene", "playwright"])) == [False, True]
    assert len(list((tmp_path / "运行").glob("[mp]*"))) == 1
