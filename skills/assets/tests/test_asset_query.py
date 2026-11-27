import hashlib
import json
from importlib import import_module

from ui_test_core.suite import selected_suite


def test_asset_version_and_scope(tmp_path):
    owner = selected_suite().load_package("assets")
    catalog = import_module(owner.__name__ + ".asset_revision").AssetCatalog(tmp_path)
    data = b"def open_page(): pass"
    (tmp_path / "entry.py").write_bytes(data)
    (tmp_path / "recover.py").write_bytes(data)
    scope = dict(project_group="sample", product="catalog", system="demo", module_path=["page"],
                 function="open", checkpoint=None, environment="test", risk_level="read",
                 case_id="caseA", step_id="OPEN")
    row = dict(symbol="open_page", sha256=hashlib.sha256(data).hexdigest(), kind="navigation",
               source="entry.py", recovery_source="recover.py", version=1, enabled=True,
               dependencies=[], steps=["OPEN"], conditions={"environment": "test"}, paused_scopes=[],
               owner={"project_group": "sample", "product": "catalog"}, side_effects="read")
    (tmp_path / "reuse-project.json").write_text(json.dumps(dict(directory=".", assets={"open": row})))
    (tmp_path / "unknown.py").write_text("def other(): pass")
    catalog.publish("open", dict(row, version=2), data, expected_revision=0)
    catalog.pause("open", 1, {"case_id": "caseA"}, expected_revision=1)
    result = owner.query(tmp_path, "open", scope, dict(approved=True, scope=scope, effects=["read"]))
    assert result["decision"]["asset"]["version"] == 2
    assert result["decision"]["scope"] == scope and result["decision"]["tier"] == "dedicated"
    assert result["pauses"] == [dict(asset_id="open", version=1, scope={"case_id": "caseA"})]
    assert any(r["status"] == "candidate" for r in result["pending"])
    assert result["calls"] == ["assets"] and result["business_attempts_added"] == 0
    assert owner.query(tmp_path, "open", {}, {})["missing"]
