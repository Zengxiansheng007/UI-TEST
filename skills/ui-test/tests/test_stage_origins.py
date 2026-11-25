import json
from scripts.ui_test_core.artifact_layout import ProjectLayout
from scripts.ui_test_core.stage_events import stage_started


def test_formal_origin_is_captured_at_start_and_never_guessed(tmp_path, monkeypatch):
    owner = [dict(case_id="A", branch_id="main")]
    layout = ProjectLayout(tmp_path)
    exploration = layout.reserve_run("midscene", "M1")
    observations = dict(stage="midscene", run_id="M1", cases=[])
    (exploration / "observations.json").write_text(json.dumps(observations), "utf8")
    (exploration / "execution-summary.json").write_text(json.dumps(observations), "utf8")
    (exploration / "report.html").write_text("M1", "utf8")
    monkeypatch.setenv("UI_TEST_EXPLORATION_RUN_ID", "M1")
    for stage in ("P1","P2"):
        stage_started(tmp_path, "playwright", stage, None, owner)
        start = json.loads((layout.run_dir("playwright",stage)/"start.json").read_text("utf8"))
        assert start["origin"]["stage_id"] == "M1"
        assert (tmp_path/start["origin"]["report"]).read_text() == "M1"
    from scripts.ui_test_core.run_catalog import register_stage
    register_stage(tmp_path, dict(stage_id="M1", stage_type="midscene", started_at=None, ended_at=None,
                                  status="observed", report_ref=(exploration/"report.html").relative_to(tmp_path).as_posix(),
                                  cases=[dict(case_id="A",branch_id="main",status="observed",attempts=[])]))
    catalog = (tmp_path/"index.html").read_text("utf8")
    assert 'id="stage-M1"' in catalog and "P1（报告待生成）" in catalog and "P2（报告待生成）" in catalog
    monkeypatch.delenv("UI_TEST_EXPLORATION_RUN_ID")
    monkeypatch.setenv("UI_TEST_STAGE_ORIGIN", "independent")
    stage_started(tmp_path, "playwright", "P3", None, owner)
    monkeypatch.delenv("UI_TEST_STAGE_ORIGIN")
    stage_started(tmp_path, "playwright", "P4", None, owner)
    assert json.loads((layout.run_dir("playwright","P3")/"start.json").read_text("utf8"))["origin"]["kind"] == "independent"
    assert json.loads((layout.run_dir("playwright","P4")/"start.json").read_text("utf8"))["origin"]["kind"] == "unknown"
