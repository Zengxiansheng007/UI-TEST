import json
from copy import deepcopy

import pytest

from test_project_asset_discovery import project
from ui_test_core.reusable_assets import select_asset


SCOPE = dict(project_group="public-tca-todomvc-20261117", product="todomvc", system="web",
             module_path=["todos"], function="basic", checkpoint=None, environment="test",
             risk_level="r2-ui-write-test", case_id="TODO-P0-002", step_id="OPEN")


def choose(project, binding=None, scope=SCOPE, **permissions):
    grant = dict(approved=True, scope=dict(scope), effects=["navigation", "read"],
                 explore=True, exploration_effect="read", facts=["page_available"])
    grant.update(permissions)
    return select_asset(project, "flow.open-todomvc", scope, grant, binding=binding)


def save_variants(project, **variants):
    path = project / "reuse-project.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    original = deepcopy(config["assets"]["flow.open-todomvc"])
    for name, edits in variants.items():
        config["assets"][name] = dict(original, capability="flow.open-todomvc", **edits)
    path.write_text(json.dumps(config), encoding="utf-8")


def test_priority_and_conflict(project):
    save_variants(project, common={"sharing": "shared"}, twin={}, stage={"conditions": {"environment": "stage"}})
    assert choose(project, "common")["asset_id"] == "common"
    decision = choose(project)
    assert decision["status"] == "conflict" and decision["step_id"] == "OPEN"
    assert set(decision["conflicts"]) == {"twin", "flow.open-todomvc"}
    assert "conditions" in decision["skipped"]["stage"]
    assert choose(project, "stage")["status"] == "blocked"
    assert choose(project, "absent")["status"] == "blocked"


def test_scope_dependency_and_grant(project):
    save_variants(project, common={"sharing": "shared"}, other={"owner": {"project_group": "another", "product": "todomvc"}})
    path = project / "reuse-project.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    nav = config["assets"]["flow.open-todomvc"]
    nav["conditions"] = {k: SCOPE[k] for k in ("project_group", "product", "system", "module_path", "function",
                                                "checkpoint", "environment", "risk_level")}
    nav["dependencies"] = ["locator.rows"]
    path.write_text(json.dumps(config), encoding="utf-8")
    assert choose(project)["tier"] == "dedicated"
    for field, value in nav["conditions"].items():
        mismatch = dict(SCOPE, **{field: ["other"] if isinstance(value, list) else "other"})
        assert choose(project, "flow.open-todomvc", mismatch)["status"] == "blocked"
    assert choose(project)["skipped"]["other"].endswith("different project")
    assert choose(project, facts=[])["status"] == "exploration_allowed"
    assert choose(project, facts=[], explore=False)["status"] == "blocked"
    assert choose(project, approved=False)["status"] == "blocked"
    grant = dict(scope=dict(SCOPE, case_id="wrong"), approved=True, effects=["read", "navigation"], facts=["page_available"])
    assert select_asset(project, "flow.open-todomvc", SCOPE, grant)["reason"] == "case_scope_not_authorized"
    config["assets"]["locator.rows"]["paused_scopes"] = [{"case_id": "TODO-P0-002"}]
    path.write_text(json.dumps(config), encoding="utf-8")
    assert choose(project)["asset_id"] == "common"
    assert "locator.rows: paused" in choose(project, "flow.open-todomvc")["skipped"]["flow.open-todomvc"]
    assert choose(project, "flow.open-todomvc", effects=[])["status"] == "blocked"


def test_legacy_unknown_effect_and_unauthorized_miss(project):
    path = project / "reuse-project.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["assets"]["flow.open-todomvc"]["side_effects"] = "unknown"
    path.write_text(json.dumps(config), encoding="utf-8")
    rejected = choose(project, effects=["unknown"])
    assert rejected["status"] == "blocked"
    assert "effect not authorized" in rejected["skipped"]["flow.open-todomvc"]
    assert choose(project, effects=[])["status"] == "blocked"


def test_transitive_prerequisite_and_cycle(project):
    path = project / "reuse-project.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["assets"]["flow.open-todomvc"]["dependencies"] = ["component.ready"]
    path.write_text(json.dumps(config), encoding="utf-8")
    assert "component.ready: step outside" in choose(project, "flow.open-todomvc")["skipped"]["flow.open-todomvc"]
    config["assets"]["component.ready"]["steps"].append("OPEN")
    config["assets"]["locator.rows"]["prerequisites"] = ["signed_in"]
    path.write_text(json.dumps(config), encoding="utf-8")
    assert "locator.rows: prerequisites" in choose(project, "flow.open-todomvc")["skipped"]["flow.open-todomvc"]
    config["assets"]["locator.rows"]["dependencies"] = ["flow.open-todomvc"]
    path.write_text(json.dumps(config), encoding="utf-8")
    result = choose(project, "flow.open-todomvc", facts=["signed_in", "page_available"])
    assert "cyclic dependency" in result["skipped"]["flow.open-todomvc"]

