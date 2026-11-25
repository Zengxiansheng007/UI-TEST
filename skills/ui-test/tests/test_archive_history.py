import json
import sqlite3
from pathlib import Path

import pytest

from test_stage_release import setup, archived, write
from test_stage_archive import project_with_stage
from scripts.ui_test_core.run_catalog import refresh_catalog
from scripts.ui_test_core.stage_release import release


def test_rebuild_offline_then_restore_historical_plan_separately_from_current_script(tmp_path):
    project, sid, _ = setup(tmp_path)
    stage_file = next((project/"运行").glob("*/stage.json"))
    stage = json.loads(stage_file.read_bytes())
    stage["started_at"] = "2019-12-31T18:00:00Z"
    write(stage_file,stage)
    binding = stage["cases"][0]["attempts"][0]["binding"]
    historical = (project/binding["entry"]).read_bytes()
    current = project/"current.py"
    current.write_text("def test_current(): pass\n",encoding="utf8")
    write(project/"current-cases.json",{"cases":[dict(case_id="A",branch_id="main",display_name="当前 A",node_id="current.py::test_current")]})
    approval, original = archived(project,sid)
    release(project,approval.stem)
    receipts = list((project/"治理/历史").glob("*.json"))
    assert len(receipts)==1
    assert json.loads(receipts[0].read_bytes())["manifest_sha256"]==original["manifest_sha256"]
    (project/"治理/归档").rename(tmp_path/"journals-unavailable")
    media = tmp_path/"media"
    unavailable = tmp_path/"unavailable"
    media.rename(unavailable)
    for path in (project/"runs.sqlite3",project/"index.html"):
        path.unlink(missing_ok=True)
    first = refresh_catalog(project)
    html = first.read_text("utf8")
    assert sid in html and "介质离线" in html and "2020-01-01" in html and binding["version"] in html
    with sqlite3.connect(project/"runs.sqlite3") as db:
        rows = db.execute("SELECT case_id,local_date,status,version,media_status,archive_dir FROM archived_runs WHERE stage_id=? ORDER BY case_id",(sid,)).fetchall()
        assert rows==[(case,"2020-01-01","observed",binding["version"],"offline",original["archive_dir"]) for case in ("A","B")]
    unavailable.rename(media)
    from scripts.ui_test_core.archive_history import restore_stage
    with pytest.raises(ValueError):
        restore_stage(project,sid,project/"运行")
    restored = restore_stage(project,sid,tmp_path/"restored")
    assert restored.name=="index.html" and restored.is_file()
    assert restore_stage(project,sid,tmp_path/"restored")==restored
    manifest=json.loads((restored.parent/"manifest.json").read_bytes())
    old_script=restored.parent/manifest["files"][binding["entry"]]["archived_ref"]
    assert old_script.read_bytes()==historical
    media.rename(unavailable)
    refresh_catalog(project)
    html=first.read_text("utf8")
    assert restored.as_uri() in html and old_script.as_uri() in html and 'href="./current.py"' in html
    assert current.read_text("utf8")=="def test_current(): pass\n"


def test_restore_never_writes_into_project_or_another_stage_archive(tmp_path):
    from scripts.ui_test_core.archive_history import restore_stage
    project,sid,_ = setup(tmp_path)
    approval,_ = archived(project,sid)
    release(project,approval.stem)
    peer = tmp_path/"peer"
    peer_medium = tmp_path/"peer-medium"
    other_sid,_ = project_with_stage(peer,peer_medium)
    _,other = archived(peer,other_sid)
    sealed = Path(other["archive_dir"])
    previous = restore_stage(project,sid,tmp_path/"safe")
    pointer = next((project/"治理/恢复").glob("*.json"))
    original_pointer = pointer.read_bytes()
    original_files = {p.relative_to(sealed):p.read_bytes() for p in sealed.rglob("*") if p.is_file()}
    settings = project/"governance-settings.json"
    configuration = json.loads(settings.read_bytes())
    new_medium = tmp_path/"new-medium"
    historical_project = tmp_path/"original-work"
    write(settings,dict(configuration,archive_destination=str(new_medium),original_project_root=str(historical_project)))
    for destination in (sealed,sealed/"inside",peer_medium/"sibling",tmp_path/"media"/"sibling",new_medium/"inside",
                        historical_project/"inside",peer/"inside",previous.parent/"inside",tmp_path):
        with pytest.raises(ValueError, match="E_RESTORE_DESTINATION"):
            restore_stage(project,sid,destination)
        assert pointer.read_bytes() == original_pointer
    assert original_files == {p.relative_to(sealed):p.read_bytes() for p in sealed.rglob("*") if p.is_file()}
    assert not new_medium.exists() and not historical_project.exists() and not (peer/"inside").exists()
    assert restore_stage(project,sid,tmp_path/"safe") == previous
