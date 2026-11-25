import json
from pathlib import Path
from hashlib import sha256
import pytest

from test_stage_archive import project_with_stage, write
from scripts.ui_test_core.retention_preview import publish_preview
from scripts.ui_test_core.stage_archive import approve, archive, verify_archive
from scripts.ui_test_core.stage_release import release


def setup(root):
    project=root/"work"
    sid, picture=project_with_stage(project,root/"media")
    return project, sid, picture


def archived(project, sid):
    approval=approve(project,publish_preview(project).stem,[sid])
    result=json.loads(archive(project,approval.stem).read_bytes())
    return approval,result["stages"][sid]


def test_release_preserves_existing_asset_user_and_records_exact_scope(tmp_path):
    project,sid,picture=setup(tmp_path)
    write(project/"reuse-project.json",dict(assets={"review":dict(enabled=True,source=picture.relative_to(project).as_posix())}))
    approval,archive_row=archived(project,sid)
    original=picture.read_bytes()
    receipt=release(project,approval.stem)
    body=json.loads(receipt.read_bytes())
    item=body["stages"][sid]
    assert item["status"]=="released" and item["released_paths"]
    assert set(item["released_paths"])<=set(json.loads(approval.read_bytes())["release_paths"][sid])
    assert set(item["released_paths"])==set(archive_row["release_paths"])
    assert all(not (project/ref).exists() for ref in item["released_paths"])
    assert picture.read_bytes()==original and picture.relative_to(project).as_posix() in item["kept_paths"]
    assert verify_archive(Path(item["archive_dir"]))["stage"]["stage_id"]==sid
    assert item["stage"]["cases"][1]["case_id"]=="B"
    assert json.loads(release(project,approval.stem).read_bytes())==body


def test_late_protection_and_changed_contents_keep_entire_stage(tmp_path):
    project,sid,picture=setup(tmp_path)
    approval,row=archived(project,sid)
    settings=project/"governance-settings.json"
    data=json.loads(settings.read_bytes())
    write(settings,dict(data,protected_stages={sid:"review baseline"}))
    result=json.loads(release(project,approval.stem).read_bytes())["stages"][sid]
    assert result["status"]=="blocked" and any(r.get("code")=="protected_stage" for r in result["reasons"])
    write(settings,data)
    picture.write_bytes(picture.read_bytes()+b"changed")
    result=json.loads(release(project,approval.stem).read_bytes())["stages"][sid]
    assert result["status"]=="blocked" and not result["released_paths"]
    assert all((project/ref).is_file() for ref in row["release_paths"])


def test_receipt_and_package_must_still_match(tmp_path):
    project,sid,picture=setup(tmp_path)
    approval,row=archived(project,sid)
    folder=Path(row["archive_dir"])
    packed=verify_archive(folder)["files"][picture.relative_to(project).as_posix()]["archived_ref"]
    (folder/packed).write_bytes(b"x"*picture.stat().st_size)
    result=json.loads(release(project,approval.stem).read_bytes())["stages"][sid]
    assert result["status"]=="blocked" and any("E_ARCHIVE_FILE_DIGEST" in r["reason"] for r in result["reasons"])
    assert all((project/ref).is_file() for ref in row["release_paths"])


@pytest.mark.parametrize("legacy",[False,True])
def test_reselected_revision_preserves_previous_archive_and_reuses_identical_version(tmp_path, legacy):
    project,sid,_=setup(tmp_path)
    approval,first=archived(project,sid)
    folder=Path(first["archive_dir"])
    if legacy:
        original_folder=folder.with_name("s"+sha256(sid.encode()).hexdigest()[:16])
        folder.rename(original_folder)
        receipt=project/"治理"/"归档"/approval.stem/"result.json"
        document=json.loads(receipt.read_bytes())
        document["stages"][sid]["archive_dir"]=str(original_folder)
        write(receipt,document)
        same=json.loads(archive(project,approval.stem).read_bytes())["stages"][sid]
        assert same["status"]=="verified" and same["archive_dir"]==str(original_folder)
        folder=original_folder
    original={p.name:p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    old=verify_archive(folder)
    report=project/old["report_ref"]
    report.write_bytes(report.read_bytes()+b"<!-- reviewer amendment -->")
    assert json.loads(release(project,approval.stem).read_bytes())["stages"][sid]["status"]=="blocked"
    updated,second=archived(project,sid)
    assert second["status"]=="verified" and second["archive_dir"]!=str(folder)
    current=Path(second["archive_dir"])
    again=archive(project,updated.stem)
    repeated=json.loads(again.read_bytes())["stages"][sid]
    assert repeated==second
    another,identical=archived(project,sid)
    assert another!=updated and identical==second
    assert verify_archive(current)["files"][old["report_ref"]]["sha256"]!=old["files"][old["report_ref"]]["sha256"]
    assert json.loads(release(project,updated.stem).read_bytes())["stages"][sid]["status"]=="released"
    assert original=={p.name:p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    assert verify_archive(folder)==old
