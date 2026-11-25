from scripts.ui_test_core.execution_version import bind_python


def test_unpublished_entry_and_transitive_dependency_are_recoverable(tmp_path):
    entry = tmp_path / "test_case.py"
    helper = tmp_path / "shared.py"
    entry.write_text("import shared\ndef test_case(): assert shared.ready()\n")
    helper.write_text("def ready(): return True\n")
    old = bind_python(tmp_path, entry, "test_case.py::test_case", [])
    assert bind_python(tmp_path, entry, old["node_id"], []) == old
    helper.write_text("def ready(): return False\n")
    new = bind_python(tmp_path, entry, old["node_id"], [])
    assert old["version"] != new["version"]
    assert old["entry"] == new["entry"]
    assert (tmp_path / old["dependencies"][0]["entry"]).read_text() == "def ready(): return True\n"
    entry.write_text("def test_case(): pass\n")
    assert (tmp_path / old["entry"]).read_text().startswith("import shared")


def test_activated_successor_does_not_rebind_previous_attempt(tmp_path, monkeypatch):
    import json
    from scripts.ui_test_core.artifact_layout import ProjectLayout
    from scripts.ui_test_core.legacy_inventory import discover_legacy
    from tests import fixtures_v2
    from tests.test_release_verifier_v2 import _write_release

    owner = ("DEMO-CASE-A", "primary")
    branch = ProjectLayout(tmp_path).register_case(*owner, "sample")
    entry = tmp_path / "runner.py"
    def activate():
        compiled, _ = fixtures_v2.compiled_v2(tmp_path / "fixture.json")
        sha = compiled["manifest"]["build_fingerprint"]
        directory = branch / "releases" / sha.split(":")[1]
        _write_release(directory, compiled)
        (branch / "active.json").write_text(json.dumps(dict(schema_version="ui-test.active-pointer.v2",
            case_id=owner[0], branch_id=owner[1], build_fingerprint=sha,
            manifest_ref=f"releases/{directory.name}/manifest.json")))
        entry.write_bytes((directory / "playwright-test.py").read_bytes())
        return bind_python(tmp_path, entry, "runner.py::test_selected", [], owner=owner)

    old = activate()
    original_bytes = entry.read_bytes()
    compile_case = fixtures_v2.compile_case_v2
    def changed_config(**kwargs):
        kwargs["config_fingerprint"] = "sha256:" + "2" * 64
        return compile_case(**kwargs)
    monkeypatch.setattr(fixtures_v2, "compile_case_v2", changed_config)
    new = activate()
    active, = [row for row in discover_legacy(tmp_path) if row["status"] == "current"]
    assert active["path"] == new["entry"] and new["release"] != old["release"]
    assert old["version"] == old["release"]
    assert (tmp_path / old["entry"]).read_bytes() == original_bytes
    assert (tmp_path / new["entry"]).read_bytes() != original_bytes

