import json
from pathlib import Path
import pytest
from test_stage_archive import project_with_stage,write
from scripts.ui_test_core import stage_archive,stage_release
from scripts.ui_test_core.retention_preview import publish_preview


def approved(tmp):
    root=tmp/"project"
    sid,photo=project_with_stage(root,tmp/"media")
    write(root/"reuse-project.json",dict(assets={"active":dict(enabled=True,source=photo.relative_to(root).as_posix())}))
    aid=stage_archive.approve(root,publish_preview(root).stem,[sid]).stem
    return root,sid,photo,aid


def test_resume_copy_uses_existing_objects_and_one_manifest(tmp_path,monkeypatch):
    root,sid,photo,aid=approved(tmp_path)
    original=stage_archive.copy_object
    copied=[]
    def stop(source,target,row):
        if copied:
            raise KeyboardInterrupt
        original(source,target,row)
        copied.append((target,target.stat().st_mtime_ns))
    with monkeypatch.context() as m:
        m.setattr(stage_archive,"copy_object",stop)
        with pytest.raises(KeyboardInterrupt):
            stage_archive.archive(root,aid)
    result=root/"治理"/"归档"/aid/"result.json"
    partial=json.loads(result.read_bytes())
    assert not partial["complete"] and partial["stages"][sid]["copied_paths"]
    row=json.loads(stage_archive.archive(root,aid).read_bytes())["stages"][sid]
    assert row["status"]=="verified" and len(list((tmp_path/"media").rglob("manifest.json")))==1
    assert copied[0][0].stat().st_mtime_ns==copied[0][1] and photo.is_file()


@pytest.mark.parametrize("protect",[False,True])
def test_resume_release_rechecks_missing_or_completed_intent_without_double_unlink(tmp_path,monkeypatch,protect):
    root,sid,photo,aid=approved(tmp_path)
    stage_archive.archive(root,aid)
    original=stage_release.unlink_work_file
    calls=[]
    def stop(*args):
        original(*args)
        calls.append(args[1])
        if len(calls)==2:
            raise KeyboardInterrupt
    with monkeypatch.context() as m:
        m.setattr(stage_release,"unlink_work_file",stop)
        with pytest.raises(KeyboardInterrupt):
            stage_release.release(root,aid)
    receipt=root/"治理"/"归档"/aid/"release.json"
    assert set(e["status"] for e in json.loads(receipt.read_bytes())["journal"].values())=={"released","releasing"}
    settings=root/"governance-settings.json"
    policy=json.loads(settings.read_bytes())
    if protect:
        write(settings,dict(policy,protected_stages={sid:"pending defect"}))
        paused=json.loads(stage_release.release(root,aid).read_bytes())["stages"][sid]
        assert paused["status"]=="blocked" and set(paused["released_paths"])==set(calls)
        assert any(r.get("code")=="protected_stage" for r in paused["reasons"])
        write(settings,policy)
    outcome=json.loads(stage_release.release(root,aid).read_bytes())
    row=outcome["stages"][sid]
    assert outcome["complete"] and row["status"]=="released" and set(calls)<set(row["released_paths"])
    assert all(not (root/ref).exists() for ref in row["released_paths"])
    assert photo.is_file() and stage_archive.verify_archive(Path(row["archive_dir"]))["stage"]["stage_id"]==sid


def test_resume_refuses_unapproved_entry_and_rechecks_reconnected_media(tmp_path,monkeypatch):
    root,sid,photo,aid=approved(tmp_path)
    archived=json.loads(stage_archive.archive(root,aid).read_bytes())["stages"][sid]
    archive_dir=Path(archived["archive_dir"])
    real=stage_release.unlink_work_file
    def interrupt(root,ref,fact):
        real(root,ref,fact)
        raise KeyboardInterrupt
    with monkeypatch.context() as patch:
        patch.setattr(stage_release,"unlink_work_file",interrupt)
        with pytest.raises(KeyboardInterrupt):
            stage_release.release(root,aid)
    receipt=root/"治理"/"归档"/aid/"release.json"
    before=json.loads(receipt.read_bytes())
    tampered=json.loads(receipt.read_bytes())
    shared=photo.relative_to(root).as_posix()
    tampered["journal"][shared]=next(iter(tampered["journal"].values()))
    write(receipt,tampered)
    with pytest.raises(ValueError,match="E_RELEASE_JOURNAL_SCOPE"):
        stage_release.release(root,aid)
    assert photo.is_file()
    write(receipt,before)
    parked=archive_dir.with_name("disconnected-media")
    archive_dir.rename(parked)
    paused=json.loads(stage_release.release(root,aid).read_bytes())
    assert paused["stages"][sid]["status"]=="blocked" and paused["journal"]==before["journal"]
    parked.rename(archive_dir)
    final=json.loads(stage_release.release(root,aid).read_bytes())
    assert final["stages"][sid]["status"]=="released" and photo.is_file()
