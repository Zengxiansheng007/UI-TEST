import json
from datetime import datetime, timezone

from scripts.ui_test_core.artifact_layout import ProjectLayout
from scripts.ui_test_core.retention_preview import build_preview, publish_preview


NOW = datetime(2026, 11, 25, tzinfo=timezone.utc)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf8")


def stage(project, sid, kind, end, owners, status="passed", attachments=()):
    folder = ProjectLayout(project).reserve_run(kind, sid)
    report = folder / "report.html"
    report.write_text("".join(f'<img src="../../{ref}">' for ref in attachments), encoding="utf8")
    cases = []
    for case, branch, attempts in owners:
        cases.append(dict(case_id=case,branch_id=branch,status=status if attempts else "not_executed",
                          attempts=[dict(attempt_ref=str(n),status=status,version="v1") for n in range(attempts)]))
    save(folder / "stage.json", dict(stage_id=sid,stage_type=kind,status=status,started_at=None,ended_at=end,
                                    report_ref=report.relative_to(project).as_posix(),cases=cases))
    return report.relative_to(project).as_posix()


def test_retention_ranks_distinct_executed_stages_per_branch_and_type(tmp_path):
    old = lambda day: f"2026-09-{day:02}T00:00:00Z"
    for kind in ("midscene","playwright"):
        for i in range(1,6):
            owners=[("A","main",2 if i==4 else 1)]
            if i==1 or i==5:
                owners.append(("B","rare",1 if i==1 else 0))
            stage(tmp_path,kind+str(i),kind,old(i),owners,"failed" if i==2 else "passed")
    stage(tmp_path,"alt","playwright",old(1),[("A","other",1)])
    stage(tmp_path,"fresh","playwright","2026-11-24T00:00:00Z",[])
    stage(tmp_path,"boundary","playwright","2026-10-26T00:00:00Z",[])
    stage(tmp_path,"bad","playwright",None,[])
    stage(tmp_path,"running","playwright",None,[("A","main",1)],"running")
    data = build_preview(tmp_path,now=NOW)
    for kind in ("midscene","playwright"):
        assert [data["stages"][kind+str(i)]["decision"] for i in range(1,6)] == ["retain","candidate","retain","retain","retain"]
        assert any(r.get("case_id") == "B" for r in data["stages"][kind+"1"]["reasons"])
    assert {sid:data["stages"][sid]["decision"] for sid in ("alt","fresh","boundary","bad","running")} == dict(
        alt="retain",fresh="retain",boundary="candidate",bad="review",running="retain")
    save(tmp_path/"governance-settings.json",dict(retention_days=0,recent_per_branch=0))
    adjusted=build_preview(tmp_path,now=NOW)
    assert adjusted["stages"]["alt"]["decision"]=="candidate"
    assert adjusted["stages"]["fresh"]["decision"]=="candidate"


def test_shared_paths_protect_and_preview_leaves_originals(tmp_path):
    scratch=tmp_path/"临时"
    scratch.mkdir()
    for name in ("shared","held","both"):
        (scratch/name).write_text(name)
    refs = {"retained":("临时/shared",),"one":("临时/shared","临时/both"),"two":("临时/both",),"by-file":("临时/held",)}
    originals={}
    for sid,links in refs.items():
        ref=stage(tmp_path,sid,"playwright","2026-01-01T00:00:00Z",[("A","main",1)],attachments=links)
        originals[ref]=(tmp_path/ref).read_bytes()
    stage(tmp_path,"missing","midscene","2026-01-01T00:00:00Z",[("B","main",1)],attachments=["临时/missing"])
    save(tmp_path/"governance-settings.json",dict(retention_days=0,recent_per_branch=0,
         protected_stages={"retained":"验收基线"},protected_files={"临时/held":"待查缺陷"},
         archive_destination=str(tmp_path.parent/"archive")))
    first=publish_preview(tmp_path,now=NOW)
    second=publish_preview(tmp_path,now=NOW)
    assert first!=second and first.exists() and second.exists()
    data=json.loads(first.with_suffix(".json").read_text("utf8"))
    assert data["stages"]["by-file"]["decision"]=="retain"
    assert data["stages"]["missing"]["decision"]=="review"
    assert data["stages"]["retained"]["decision"]=="retain"
    assert "临时/shared" in data["stages"]["one"]["keep_files"]
    assert "临时/both" in data["stages"]["one"]["proposed_release"]
    assert data["files"]["临时/both"]["required_stages"]==["one","two"]
    assert len(data["files"]["临时/both"]["sha256"])==64
    assert "验收基线" in first.read_text("utf8")
    assert all((tmp_path/ref).read_bytes()==content for ref,content in originals.items())


def test_completed_cycle_reuses_original_despite_input_change(tmp_path):
    import pytest
    from scripts.ui_test_core.inventory_report import publish_inventory
    stage(tmp_path,"older","midscene","2025-01-01T00:00:00Z",[("A","b",1)])
    config = tmp_path/"governance-settings.json"
    save(config,dict(retention_days=0,recent_per_branch=0))
    publish_inventory(tmp_path)
    page = publish_preview(tmp_path,now=NOW,request_id="schedule:cycle-1")
    assert "历次待审清单" in (tmp_path/"index.html").read_text("utf8")
    data = page.with_suffix(".json")
    original = [path.read_bytes() for path in (page,data)]
    save(config,dict(retention_days=0,recent_per_branch=0,protected_stages={"older":"保护"}))
    assert publish_preview(tmp_path,now=NOW,request_id="schedule:cycle-1")==page
    assert original == [path.read_bytes() for path in (page,data)]
    next_page = publish_preview(tmp_path,now=NOW,request_id="schedule:cycle-2")
    assert json.loads(next_page.with_suffix(".json").read_text("utf8"))["stages"]["older"]["decision"]=="retain"
    assert next_page != page
    next_page.rename(tmp_path/"interrupted-page.html")  # Retain the first attempt and leave only its uncommitted JSON.
    restored = publish_preview(tmp_path,now=NOW,request_id="schedule:cycle-2")
    assert restored == next_page and restored.is_file()
    manual = publish_preview(tmp_path,now=NOW)
    assert (json.loads(manual.with_suffix(".json").read_text("utf8"))["stages"]
            == json.loads(restored.with_suffix(".json").read_text("utf8"))["stages"])
    with pytest.raises(ValueError, match="E_PREVIEW_REQUEST_ID"):
        publish_preview(tmp_path,request_id="unscoped")
