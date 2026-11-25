import html
import json

from scripts.ui_test_core.artifact_inventory import inventory_project
from scripts.ui_test_core.run_catalog import register_stage


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")


def test_inventory_uses_original_reference_bases_and_distinct_consumers(tmp_path):
    from scripts.ui_test_core.artifact_layout import ProjectLayout
    stage = ProjectLayout(tmp_path).run_dir("playwright", "actual-1")
    stage.mkdir(parents=True)
    scratch = tmp_path / "临时"
    scratch.mkdir()
    shared = scratch / "shared.png"
    shared.write_bytes(b"four")
    (scratch / "cache.bin").write_bytes(b"cache")
    dump(scratch / "_PRIVATE" / "no.json", {"private": True})
    report = stage / "report.html"
    ownership = [dict(case_id=c, branch_id="main",step_id=s,attempt_ref="1",path=str(shared))
                 for c,s in [("A","confirm"),("B","review")]]
    report.write_text("".join('<button data-image-metadata="'+html.escape(json.dumps(i))+'"></button>' for i in ownership))
    root = stage / "a1"
    result = root / "finalization/objects/result.json"
    dump(result, dict(schema_version="ui-test.run-result.v5",run_id="r",case_id="A",branch_id="main",
                      step_results=[dict(step_id="submit",evidence_refs=["reports/missing.png"])],evidence_refs=[]))
    relative = lambda path:path.relative_to(tmp_path).as_posix()
    register_stage(tmp_path, dict(stage_id="actual-1",stage_type="playwright",started_at=None,ended_at=None,
                   status="failed",report_ref=relative(report),cases=[
                       dict(case_id=c,branch_id="main",status="passed",attempts=[
                           dict(attempt_ref="1",status="passed",version="v1",execution_ref=relative(result) if c=="A" else None,evidence_ref=None)]) for c in ("A","B")]))
    dump(tmp_path / "legacy-sources.json", {"directories":["old"]})
    for batch in ("retired","chosen"):
        path = tmp_path / "old" / batch
        path.mkdir(parents=True)
        (path / "report.html").write_text("historical")
    dump(tmp_path / "governance-settings.json", {"legacy_batches":{"old-2":"old/chosen"},"archive_destination":"Z:/disconnected"})
    data = inventory_project(tmp_path)
    files = {item["path"]:item for item in data["files"]}
    shared_row = files["临时/shared.png"]
    assert shared_row["category"]=="evidence" and shared_row["size"]==4
    assert {(c["case_id"],c["step_id"]) for c in shared_row["consumers"]}=={("A","confirm"),("B","review")}
    assert files["临时/cache.bin"]["eligibility"]=="inventory_only"
    assert files["old/retired/report.html"]["eligibility"]=="inventory_only"
    assert files["old/chosen/report.html"]["legacy_batches"]==["old-2"]
    assert not any("no.json" in key for key in files)
    assert any(i["stage_id"]=="actual-1" and i["step_id"]=="submit" and i["path"].endswith("a1/reports/missing.png") for i in data["issues"])
    assert sum(row["count"] for row in data["categories"])==len(files)
    assert sum(row["bytes"] for row in data["categories"])==sum(row["size"] for row in files.values())


def test_active_consumers_and_frozen_versions(tmp_path):
    from scripts.ui_test_core.artifact_layout import ProjectLayout
    from scripts.ui_test_core.inventory_report import publish_inventory
    source = tmp_path / "lib/shared.py"
    source.parent.mkdir()
    source.write_text("shared")
    dump(tmp_path / "reuse-project.json", dict(directory="lib", assets={
        "shared": dict(enabled=True, version="a", source="shared.py", steps=["generic"]),
        "review": dict(enabled=True, version="b", steps=["inspect"], dependencies=["shared"])}))
    stage = ProjectLayout(tmp_path).reserve_run("midscene", "exploration")
    other = tmp_path / "版本/plan.json"
    dump(other, {"plan":True})
    cases = []
    for name in ("A","B"):
        cases.append(dict(case_id=name,branch_id=name,status="observed",attempts=[
            dict(status="observed",attempt_ref="1",version="frozen",
                 binding=dict(entry="版本/plan.json",dependencies=[],source="original.json",node_id="explore",sha256="0"*64),
                 execution_ref=None,evidence_ref=None)]))
    register_stage(tmp_path, dict(stage_id="exploration",stage_type="midscene",status="observed",
                   started_at=None,ended_at=None,report_ref=None,cases=cases))
    publish_inventory(tmp_path)
    data = json.loads((tmp_path / "治理/inventory.json").read_text("utf8"))
    rows = {row["path"]:row for row in data["files"]}
    assert {p["asset_id"] for p in rows["lib/shared.py"]["consumers"]} == {"shared","review"}
    assert {p["step_id"] for p in rows["lib/shared.py"]["consumers"]} == {"generic","inspect"}
    assert {p["case_id"] for p in rows["版本/plan.json"]["consumers"]} == {"A","B"}
    assert "查看项目产物盘点" in (tmp_path/"index.html").read_text("utf8")
    assert "执行时入口" in (tmp_path/"index.html").read_text("utf8")


def test_inventory_preserves_unsealed_events_and_shared_version_after_refresh(tmp_path):
    from scripts.ui_test_core.artifact_layout import ProjectLayout
    from scripts.ui_test_core.execution_version import bind_exploration
    from scripts.ui_test_core.inventory_report import publish_inventory
    from scripts.ui_test_core.run_catalog import refresh_catalog
    from scripts.ui_test_core.stage_events import stage_started, record_attempt
    stage_id = "interrupted"
    owner = {"case_id":"A","branch_id":"main"}
    stage_started(tmp_path, "midscene", stage_id, "2026-11-25T10:00:00+08:00", [owner])
    folder = ProjectLayout(tmp_path).run_dir("midscene",stage_id)
    picture = tmp_path / "临时/shared.png"
    picture.parent.mkdir()
    picture.write_bytes(b"screen")
    binding = bind_exploration(tmp_path, dict(selected_plan={"id":"read"},node_id="A"))
    attempt = dict(attempt_ref="1", status="observed", binding=binding, version=binding["version"])
    observation = dict(**owner, attempt_ref="1",steps=[dict(step_id="read",images=[dict(path=str(picture))])])
    record_attempt(tmp_path, "midscene", stage_id, owner, attempt, observation=observation)
    assert not (folder/"stage.json").exists()
    publish_inventory(tmp_path)
    data = json.loads((tmp_path/"治理/inventory.json").read_text("utf8"))
    assert data["stages"][stage_id]["status"]=="running"
    assert data["stages"][stage_id]["cases"][0]["attempts"][0]["version"]==binding["version"]
    rows = {row["path"]:row for row in data["files"]}
    assert rows[binding["entry"]]["consumers"][0]["case_id"]=="A"
    assert rows["临时/shared.png"]["consumers"][0]["step_id"]=="read"
    for _ in range(2):
        page = (tmp_path/"index.html").read_text("utf8")
        assert all(text in page for text in ("执行时入口","查看项目产物盘点","执行中，尚无收尾记录"))
        refresh_catalog(tmp_path)


def test_unselected_legacy_stage_still_owns_shared_file(tmp_path):
    shared = tmp_path / "临时/shared.png"
    shared.parent.mkdir()
    shared.write_bytes(b"x")
    dump(tmp_path / "legacy-sources.json", {"directories":["old"]})
    dump(tmp_path / "governance-settings.json", {"legacy_batches":{"selected":"old/selected"}})
    for batch in ("selected","retained"):
        stage = tmp_path / "old" / batch
        stage.mkdir(parents=True)
        (stage / "report.html").write_text('<img src="../../临时/shared.png">',encoding="utf8")
        dump(stage/"stage.json",dict(stage_id=batch,stage_type="playwright",status="passed",cases=[],
                                     report_ref="old/"+batch+"/report.html"))
    data=inventory_project(tmp_path)
    assert data["stages"]["retained"]["disposition_scope"] == "inventory_only"
    assert data["stages"]["selected"]["disposition_scope"] == "named_legacy"
    row = next(row for row in data["files"] if row["path"]=="临时/shared.png")
    assert {p["stage_id"] for p in row["consumers"]} == {"selected","retained"}


def test_wrong_legacy_stage_identity_cannot_make_any_file_eligible(tmp_path):
    dump(tmp_path/"legacy-sources.json",dict(directories=["historical"]))
    dump(tmp_path/"governance-settings.json",dict(legacy_batches={"alias":"historical/run"}))
    folder = tmp_path / "historical/run"
    dump(folder/"stage.json",dict(stage_id="actual",stage_type="playwright",status="passed",cases=[],
                                  report_ref="historical/run/report.html"))
    (folder/"report.html").write_text('<img src="../../临时/only.png">',encoding="utf8")
    picture = tmp_path / "临时/only.png"
    picture.parent.mkdir()
    picture.write_bytes(b"x")
    data = inventory_project(tmp_path)
    assert data["legacy_batches"] == {}
    assert data["stages"]["actual"]["disposition_scope"] == "inventory_only"
    assert all(row["eligibility"] == "inventory_only" and not row["legacy_batches"] for row in data["files"])
    assert any(issue.get("legacy_batch") == "alias" for issue in data["issues"])
