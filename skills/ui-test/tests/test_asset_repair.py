import pytest
import importlib.util
import json
import sys
from pathlib import Path

from ui_test_core.asset_repair import impact_plan, repair_destination, require_verified
from ui_test_core.asset_repair import restore
from ui_test_core.asset_revision import AssetCatalog, digest, encoded, replace


def test_direct_transitive_bindings_and_unresolved_dependency():
    rows = {"target": {"dependencies": []}, "ready": {"dependencies": ["target"]},
            "complete": {"dependencies": ["ready"], "dynamic_dependencies": True}}
    plan = impact_plan(rows, "target", {"A": ["ready"], "B": ["complete"], "C": []})
    assert plan["cases"] == ["A", "B"] and plan["direct"] == ["ready"]
    assert plan["transitive"] == ["complete"] and plan["unresolved"] == ["complete"]


def test_project_adapts_unknown_or_foreign_source():
    assert repair_destination("project") == "project-source"
    for owner in ("external", None):
        assert repair_destination(owner) == "project-adapter"


def test_restore_requires_verified_applicable_unpaused_version():
    scope = {"case_id": "A", "environment": "test", "step_id": "COMPLETE"}
    sha = "a" * 64
    row = dict(version=1, sha256=sha, conditions={"environment": "test"}, paused_scopes=[])
    receipt = dict(case_id="A", scope=scope, asset_id="target", version=1, sha256=sha,
                   entered=True, assertion_result="passed", action_result="passed", source_hash="b" * 64)
    require_verified("target", row, scope, receipt, source_hash="b" * 64, paused=False)
    for field, value in (("version", 2), ("entered", False), ("source_hash", "c"*64)):
        with pytest.raises(ValueError):
            require_verified("target", row, scope, {**receipt, field: value}, source_hash="b"*64, paused=False)
    for item, paused in (({**row, "conditions": {"environment": "staging"}}, False),
                         ({**row, "paused_scopes": [scope]}, False), (row, True)):
        with pytest.raises(ValueError):
            require_verified("target", item, scope, receipt, source_hash="b"*64, paused=paused)


@pytest.mark.parametrize("ownership", ["external", "unknown"])
def test_foreign_source_is_preserved_and_scoped_rollback_is_checked(tmp_path, monkeypatch, ownership):
    template = Path(__file__).resolve().parents[3] / "examples/todomvc-repair"
    monkeypatch.syspath_prepend(str(template))
    spec = importlib.util.spec_from_file_location("repair_project", template/"prepare.py")
    sample = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sample)
    def fixture_use(root, run, status):
        return json.loads((root/"runs"/run/"use.json").read_bytes()), "sha256:"+"a"*64
    monkeypatch.setattr(sample, "committed_use", fixture_use)
    project, trial = tmp_path/"project", tmp_path/"trial"
    sample.initialize(project, ownership)
    catalog = AssetCatalog(project)
    _, rows = catalog.pin()
    key, scope = sample.KEY, sample.SCOPE
    original = (project/"assets/target.py").read_bytes()
    source_hash = digest((project/"source_case.py").read_bytes())
    failure = dict(failure={"cause":"asset"}, matches=2, scope=scope, version=1, sha256=rows[key]["sha256"],
                   run_id="FAILED", source_hash=source_hash, action_result="not_attempted", writes=["add","add"])
    replace(project/"runs/FAILED/use.json", encoded(failure))
    catalog.pause(key, 1, scope, expected_revision=0)
    sample.stage(project, trial, "FAILED")
    assert (trial/"qualification.json").is_file() and original == (trial/"assets/target.py").read_bytes()
    trial_catalog = AssetCatalog(trial)
    _, tested = trial_catalog.pin()
    assert tested[key]["source"] == "project-adapter/2/target.py"
    proof = dict(asset_id=key, version=2, sha256=tested[key]["sha256"], case_id=scope["case_id"],
                 run_id="QUAL", entered=True, assertion_result="passed", action_result="passed",
                 source_hash=source_hash, scope=scope, entries=[key,"script.complete","component.ready"],
                 before=[False,False,"2 items left"], after=[True,False,"1 item left"])
    replace(trial/"runs/QUAL/use.json", encoded(proof))
    sample.promote(project, trial, "QUAL")
    assert original == (project/"assets/target.py").read_bytes()
    import ui_test_core.asset_repair as repairs
    monkeypatch.setattr(repairs, "committed_use", fixture_use)
    replace(project/"runs/ARCHIVED/use.json", encoded({**proof,"version":1,"sha256":digest(original),"run_id":"ARCHIVED"}))
    with pytest.raises(ValueError):
        restore(catalog,key,1,scope,"ARCHIVED",source_hash=source_hash,expected_revision=2)
    raw = (trial/tested[key]["recovery_source"]).read_bytes()
    catalog.publish(key,{**tested[key],"version":3},raw,expected_revision=2)
    replace(project/"runs/QUAL/use.json", encoded(proof))
    restore(catalog,key,2,scope,"QUAL",source_hash=source_hash,expected_revision=3)
    assert catalog.pin()[1][key]["version"] == 2
