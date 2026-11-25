import base64
import hashlib
import json
from pathlib import Path
import pytest

from scripts.ui_test_core.artifact_layout import ProjectLayout
from scripts.ui_test_core.execution_version import bind_exploration
from scripts.ui_test_core.retention_preview import publish_preview
from scripts.ui_test_core.stage_archive import approve, archive, verify_archive


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf8")


def project_with_stage(root, destination):
    root.mkdir()
    sid = "M-archive"
    folder = ProjectLayout(root).reserve_run("midscene",sid)
    plan = bind_exploration(root, dict(node_id="test_plan",selected_plan={"read":True}))
    sc = root / "临时" / "proof.png"
    sc.parent.mkdir()
    sc.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRqkAAAAASUVORK5CYII="))
    image=dict(path=str(sc),sha256=hashlib.sha256(sc.read_bytes()).hexdigest())
    rows, cases, html = [], [], []
    obs=folder/"observations.json"
    for sid_case,step in (("A","inspect"),("B","read")):
        case=dict(case_id=sid_case,branch_id="main",status="observed",attempt_ref="1")
        rows.append(dict(**case,steps=[dict(step_id=step,images=[image])]))
        cases.append(dict(case_id=sid_case,branch_id="main",status="observed",attempts=[dict(
            attempt_ref="1",status="observed",version=plan["version"],binding=plan,
            execution_ref=obs.relative_to(root).as_posix(),evidence_ref=obs.relative_to(root).as_posix())]))
        html.append(f'<section id="case-{len(rows)}"><header><h2>{sid_case}</h2><strong>observed · 已观察</strong></header>'
                    '<img src="../../临时/proof.png"></section>')
    report=folder/"report.html"
    report.write_text('<html><body>M-archive' + "".join(html) + '</body></html>',encoding="utf8")
    write(obs,dict(stage="midscene",run_id=sid,cases=rows))
    write(folder/"execution-summary.json",dict(stage="midscene",run_id=sid,cases=[{k:v for k,v in r.items() if k!="steps"} for r in rows]))
    write(folder/"evidence-index.json",dict(stage="midscene",run_id=sid,cases=[dict(case_id=r["case_id"],source=str(obs)) for r in rows]))
    write(folder/"stage.json",dict(stage_id=sid,stage_type="midscene",started_at=None,ended_at="2020-01-01T00:00:00Z",
                                  status="observed",cases=cases,report_ref=report.relative_to(root).as_posix()))
    write(root/"governance-settings.json",dict(retention_days=0,recent_per_branch=0,archive_destination=str(destination)))
    return sid,sc


def test_archived_reader_requires_no_originals_and_preserves_scope(tmp_path):
    project=tmp_path/"project"
    sid,picture=project_with_stage(project,tmp_path/"media")
    preview=publish_preview(project)
    approval=approve(project,preview.stem,[sid])
    assert approve(project,preview.stem,[sid])==approval
    receipt=json.loads(archive(project,approval.stem).read_text("utf8"))["stages"][sid]
    assert receipt["status"]=="verified"
    assert picture.exists()
    folder=Path(receipt["archive_dir"])
    project.rename(tmp_path/"original-unavailable")
    manifest=verify_archive(folder)
    assert manifest["stage"]["stage_id"]==sid
    photo=manifest["files"]["临时/proof.png"]
    assert {p["step_id"] for p in photo["consumers"] if p.get("step_id")}=={"inspect","read"}
    assert (folder/photo["archived_ref"]).read_bytes().startswith(b"\x89PNG")
    assert manifest["report_ref"] in manifest["files"] and (folder/"index.html").is_file()


def test_approved_missing_proof_keeps_other_originals(tmp_path):
    project=tmp_path/"project"
    sid,picture=project_with_stage(project,tmp_path/"media")
    approval=approve(project,publish_preview(project).stem,[sid])
    picture.rename(tmp_path/"isolated-missing.png")
    result=json.loads(archive(project,approval.stem).read_text("utf8"))["stages"][sid]
    assert result["status"]=="blocked" and result["release_paths"]==[]
    assert any(r.get("step_id")=="read" and r.get("path")=="临时/proof.png" for r in result["reasons"])
    assert list((project/"运行").glob("*/report.html"))


def test_conflicting_report_result_does_not_get_verified(tmp_path):
    project=tmp_path/"project"
    sid,_=project_with_stage(project,tmp_path/"media")
    report=next((project/"运行").glob("*/report.html"))
    report.write_text(report.read_text("utf8").replace("observed · 已观察","failed · 失败",1),encoding="utf8")
    approval=approve(project,publish_preview(project).stem,[sid])
    result=json.loads(archive(project,approval.stem).read_text("utf8"))["stages"][sid]
    assert result["status"]=="blocked" and any("E_ARCHIVE_REPORT_RESULT" in r["reason"] for r in result["reasons"])
    assert not list((tmp_path/"media").rglob("manifest.json"))


def test_recheck_rejects_corrupted_archived_object_and_preserves_source(tmp_path):
    project=tmp_path/"project"
    sid,source=project_with_stage(project,tmp_path/"media")
    approved=approve(project,publish_preview(project).stem,[sid])
    outcome=archive(project,approved.stem)
    stage=json.loads(outcome.read_text("utf8"))["stages"][sid]
    folder=Path(stage["archive_dir"])
    photo=verify_archive(folder)["files"]["临时/proof.png"]
    (folder/photo["archived_ref"]).write_bytes(b"x"*photo["size"])
    with pytest.raises(ValueError,match="E_ARCHIVE_FILE_DIGEST"):
        verify_archive(folder)
    assert json.loads(archive(project,approved.stem).read_text("utf8"))["stages"][sid]["status"]=="blocked"
    assert hashlib.sha256(source.read_bytes()).hexdigest()==photo["sha256"]
