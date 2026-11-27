"""Read a source-bound experience recommendation in its exact scope."""
from pathlib import Path

from .experience_store import SCOPE_FIELDS, lookup


def query(root=None, scope=None, *, project=None, asset=None, build=None):
    scope = scope if isinstance(scope, dict) else {}
    receipt = dict(calls=["experience"], business_attempts_added=0)
    if project is not None:
        from ui_test_core.reusable_assets import SELECTION_SCOPE
        from .strategy_learning import applicable_experiences

        missing = [k for k in SELECTION_SCOPE if k not in scope or (k != "checkpoint" and not scope[k])]
        if root is not None:
            raise ValueError("choose an experience root or a project strategy store")
        if not project or not Path(project).is_dir():
            missing.append("project")
        if not asset:
            missing.append("asset")
        if not build:
            missing.append("build")
        if missing:
            return dict(receipt, missing=missing)
        records = applicable_experiences(project, scope, asset, build, trial=True, include_source=True)
        return dict(receipt, records=records, incomplete=[])
    missing = [field for field in SCOPE_FIELDS if not scope.get(field)]
    if not root or not Path(root).is_dir():
        missing.append("experience_root")
    if missing:
        return dict(receipt, missing=missing)
    records = lookup(root, scope)
    supported = []
    incomplete = []
    for record in records:
        absent = [k for k in ("source_run_ids", "source_step_ids", "evidence_refs")
                  if not isinstance(record.get(k), list) or not record[k]
                  or not all(isinstance(value, str) and value.strip() for value in record[k])]
        if absent:
            incomplete.append(dict(path=record["path"], missing=absent))
        else:
            supported.append(record)
    return dict(receipt, records=supported, incomplete=incomplete)
