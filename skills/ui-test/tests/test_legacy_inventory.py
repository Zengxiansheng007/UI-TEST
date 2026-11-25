import json
import pytest

from scripts.ui_test_core.legacy_inventory import discover_legacy
from tests.fixtures_v2 import compiled_v2
from tests.test_release_verifier_v2 import _write_release


def test_scoped_discovery_verifies_active_and_opens_original(tmp_path):
    branch = tmp_path / "old/cases/DEMO-CASE-A/branches/primary"
    compiled, _ = compiled_v2(tmp_path / "fixture.json")
    build = compiled["manifest"]["build_fingerprint"]
    release = branch / "releases" / build.split(":")[1]
    _write_release(release, compiled)
    pointer = dict(schema_version="ui-test.active-pointer.v2", case_id="DEMO-CASE-A",
                   branch_id="primary", build_fingerprint=build,
                   manifest_ref=f"releases/{release.name}/manifest.json")
    (branch / "active.json").write_text(json.dumps(pointer))
    (tmp_path / "legacy-sources.json").write_text(json.dumps({"directories": ["old"]}))
    (tmp_path / "outside.py").write_text("unselected")
    for name in ["archive", "backup"]:
        folder = tmp_path / "old" / name
        folder.mkdir()
        (folder / "playwright-test.py").write_text("old")
    report = tmp_path / "old/archive/report.html"
    report.write_text('<img src="evidence/missing.png">')
    rows = discover_legacy(tmp_path)
    current = [r for r in rows if r["status"] == "current"]
    assert len(current) == 1
    assert tmp_path / current[0]["path"] == release / "playwright-test.py"
    assert current[0]["source"].endswith("active.json")
    assert not any("outside.py" in r["path"] for r in rows)
    unresolved = [r for r in rows if r["kind"] == "script" and r["status"] == "pending"]
    assert len(unresolved) == 2 and all("同名" in r["reason"] for r in unresolved)
    old = next(r for r in rows if r["kind"] == "report")
    assert (tmp_path / old["path"]).read_text() == report.read_text()
    assert "evidence/missing.png" in old["reason"]
    (release / "playwright-test.py").unlink()
    rows = discover_legacy(tmp_path)
    assert not any(r["status"] == "current" for r in rows)
    assert any(r["status"] == "missing" and r["path"].endswith("playwright-test.py") for r in rows)
    (release / "manifest.json").unlink()
    rows = discover_legacy(tmp_path)
    assert any(r["status"] == "broken" and r["source"].endswith("active.json") for r in rows)


def test_missing_directory_and_unconfigured_project(tmp_path):
    assert discover_legacy(tmp_path) == []
    config = tmp_path / "legacy-sources.json"
    config.write_text('{"directories":["absent"]}')
    missing, = discover_legacy(tmp_path)
    assert (missing["path"], missing["status"], missing["source"]) == ("absent", "missing", config.name)
    for forbidden in ["..", "_private", ".", ".git"]:
        config.write_text(json.dumps({"directories": [forbidden]}))
        with pytest.raises(ValueError, match="E_LEGACY_SCOPE"):
            discover_legacy(tmp_path)


def test_report_resolves_base_and_percent_encoded_file_in_original_directory(tmp_path):
    root = tmp_path / "old"
    media = root / "evidence"
    media.mkdir(parents=True)
    (media / "step 1.png").write_bytes(b"sample")
    (root / "report.html").write_text('<base href="evidence/"><img src="step%201.png">')
    (tmp_path / "legacy-sources.json").write_text('{"directories":["old"]}')
    report, = discover_legacy(tmp_path)
    assert report["status"] == "historical" and report["reason"] == ""
