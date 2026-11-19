"""Project-file discovery remains read-only and works after a process restart."""
import json
import base64
import hashlib
import shutil
from pathlib import Path

import pytest

from ui_test_core.reusable_assets import applicable, dependents, discover


EXAMPLE = Path(__file__).resolve().parents[3] / "examples/todomvc"


@pytest.fixture
def project(tmp_path):
    shutil.copytree(EXAMPLE / "versions", tmp_path / "versions")
    for name in ("todomvc_page.py", "reuse-project.json"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    return tmp_path


def test_unique_nested_move_and_same_name_candidate(project):
    source = project / "todomvc_page.py"
    moved = project / "components" / "renamed.py"
    moved.parent.mkdir()
    source.rename(moved)
    rows = discover(project)
    assert {r["kind"] for r in rows.values()} == {"navigation", "locator", "component", "script"}
    assert applicable(project, "flow.open-todomvc", {"environment": "test"})["source"] == "components/renamed.py"
    assert discover(project) == rows
    shutil.copy(moved, moved.with_name("duplicate.py"))
    assert discover(project)["flow.open-todomvc"]["status"] == "ambiguous"
    source.write_text("raise RuntimeError('scanning executed the file')", encoding="utf-8")
    assert discover(project)["flow.open-todomvc"]["status"] == "modified_candidate"


def test_missing_dependency_and_pause_explain_affected_steps(project):
    cfg = project / "reuse-project.json"
    doc = json.loads(cfg.read_text())
    doc["assets"]["script.complete"]["dependencies"] = ["component.ready"]
    doc["assets"]["locator.rows"]["paused_scopes"] = [{"environment": "test"}]
    cfg.write_text(json.dumps(doc))
    assert dependents(discover(project), "locator.rows") == ["component.ready", "script.complete"]
    with pytest.raises(ValueError, match="paused"):
        applicable(project, "script.complete", {"environment": "test"})
    doc["assets"]["component.ready"]["dependencies"] = ["missing.locator"]
    cfg.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="missing.locator.*COMPLETE"):
        applicable(project, "script.complete", {"environment": "test"})
    (project / doc["assets"]["script.complete"]["recovery_source"]).unlink()
    with pytest.raises(ValueError, match="missing_version.*COMPLETE"):
        applicable(project, "script.complete", {"environment": "test"})


def test_new_declaration_and_duplicate_identity_remain_static(project):
    manifest = project / "reuse-project.json"
    config = json.loads(manifest.read_text())
    asset = config["assets"].pop("component.ready")
    manifest.write_text(json.dumps(config))
    sidecar = project / "component.asset.json"
    sidecar.write_text(json.dumps({"assets": {"component.ready": asset}}))
    assert discover(project)["component.ready"]["status"] == "candidate"
    shutil.copy(sidecar, project / "duplicate.asset.json")
    conflict = discover(project)["component.ready"]
    assert conflict["status"] == "ambiguous"
    assert conflict["declarations"] == ["component.asset.json", "duplicate.asset.json"]


def test_undeclared_and_changed_sources_have_independent_recoverable_identity(project):
    new = project / "component.py"
    changed = project / "todomvc_page.py"
    new.write_bytes(b"raise RuntimeError('never import')\nclass Badge:\n    def visible(self): pass\n")
    changed.write_bytes(b"def external_open(): pass\n")
    rows = discover(project)
    by_source = {r["source"]: (k, r) for k, r in rows.items() if k.startswith("candidate:")}
    new_key, candidate = by_source["component.py"]
    assert "Badge.visible" in candidate["symbols"] and not candidate["enabled"]
    assert candidate["reason"] == "undeclared_source"
    changed_key, replacement = by_source["todomvc_page.py"]
    assert replacement["symbols"] == ["external_open"]
    assert replacement["reason"] == "externally_modified_source"
    assert rows["flow.open-todomvc"]["status"] == "modified_candidate"
    assert changed_key != new_key and changed_key != "flow.open-todomvc"
    snapshot = json.loads((project / replacement["recovery_source"]).read_text())
    assert base64.b64decode(snapshot["content_base64"]) == changed.read_bytes()
    assert replacement["sha256"] == hashlib.sha256(changed.read_bytes()).hexdigest()
    changed.unlink()
    new.unlink()
    assert discover(project)[changed_key] == replacement
    with pytest.raises(ValueError, match="candidate"):
        applicable(project, new_key, {"environment": "test"})
