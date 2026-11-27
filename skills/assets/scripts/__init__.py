"""Query project declarations and the currently effective asset revision."""
import json
from pathlib import Path

from . import reusable_assets
from .asset_revision import AssetCatalog


def query(project=None, capability=None, scope=None, authorization=None, *, binding=None):
    receipt = dict(calls=["assets"], business_attempts_added=0)
    scope = scope if isinstance(scope, dict) else {}
    missing = [k for k in reusable_assets.SELECTION_SCOPE
               if k not in scope or (k != "checkpoint" and not scope[k])]
    if not project or not (Path(project) / "reuse-project.json").is_file():
        missing.append("project/reuse-project.json")
    if not capability:
        missing.append("capability")
    if not isinstance(authorization, dict) or not authorization:
        missing.append("authorization")
    if missing:
        return dict(receipt, missing=missing)
    catalog = AssetCatalog(project)
    state = catalog.state()
    rows = reusable_assets.discover(project, state=state, persist_candidates=False)
    decision = reusable_assets.select_asset(project, capability, scope, authorization,
                                           binding=binding, pinned_rows=rows)
    relevant = {key for key, row in rows.items() if row.get("capability", key) == capability}
    if binding:
        relevant.add(binding)
    relevant.update(decision.get("dependencies", {}))
    pauses = [p for p in state["pauses"] if p["asset_id"] in relevant]
    for key in sorted(relevant.intersection(rows)):
        row = rows[key]
        pauses.extend(dict(asset_id=key, version=row["version"], scope=p)
                      for p in row.get("paused_scopes", []))
    for marker in sorted((Path(project) / "reuse-decisions/paused").glob("*.json")):
        record = json.loads(marker.read_bytes())
        if record["asset_id"] in relevant:
            pauses.append(record)
    pending = [dict(asset_id=key, status=row["status"], source=row["source"])
               for key, row in rows.items() if row["status"] != "available"]
    if catalog.revision() != state["revision"]:
        raise ValueError("asset catalog changed during query; retry the query")
    return dict(receipt, decision=decision, pending=pending, pauses=pauses, revision=state["revision"])


def repair_snapshot(project):
    """Read the selected project's immutable revision and declarations without admitting new candidates."""
    catalog = AssetCatalog(project)
    state = catalog.state()
    return catalog, state["revision"], reusable_assets.discover(project, state=state, persist_candidates=False)


def check_repair_candidate(project, rows, asset_id, scope):
    """Verify the candidate's live dependency and pause conditions in its trial project."""
    return reusable_assets._available(project, rows, asset_id, scope)
