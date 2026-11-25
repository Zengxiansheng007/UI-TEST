"""Determine the regression and restore conditions for a scoped asset repair."""
from .reusable_assets import dependents


def committed_use(project, run_id, expected_status):
    """Bind the step-use detail to the pytest transaction and its signed result."""
    import json
    from .case_contracts import canonical_hash
    from .reusable_assets import inside, trace_run
    if not run_id or not run_id.isalnum():
        raise ValueError("expected a project run identifier")
    from .artifact_layout import ProjectLayout
    root = ProjectLayout(project).find_attempt(run_id)
    uses = trace_run(root)
    final = root/"finalization"
    commit = json.loads((final/"finalization-commit.json").read_bytes())
    result = json.loads(inside(final,commit["run_result_ref"]).read_bytes())
    if len(uses) != 1 or result["overall_status"] != expected_status or result["run_id"] != run_id:
        raise ValueError("incomplete scoped run")
    steps = [step for step in result["step_results"] if step["step_id"] == uses[0]["step_id"]]
    if len(steps) != 1 or steps[0].get("asset_use_hash") != canonical_hash(uses[0]):
        raise ValueError("committed asset use digest mismatch")
    return uses[0], result["run_result_hash"]


def impact_plan(rows, asset_id, source_bindings):
    if asset_id not in rows:
        raise ValueError("unknown repair target")
    downstream = set(dependents(rows, asset_id))
    affected = downstream | {asset_id}
    direct = sorted(key for key in downstream if asset_id in rows[key]["dependencies"])
    unresolved = sorted(key for key, row in rows.items() if row.get("dynamic_dependencies")
                        or (key in affected and any(dep not in rows for dep in row["dependencies"])))
    return dict(direct=direct, transitive=sorted(downstream.difference(direct)),
                cases=sorted(case for case, bindings in source_bindings.items() if affected.intersection(bindings)),
                unresolved=unresolved)


def repair_destination(ownership):
    return "project-source" if ownership == "project" else "project-adapter"


def require_verified(asset_id, row, scope, receipt, *, source_hash, paused):
    """Check a version's scoped regression proof before promotion or restore."""
    expected = dict(asset_id=asset_id, version=row["version"], sha256=row["sha256"], scope=scope,
                    case_id=scope["case_id"], source_hash=source_hash, entered=True,
                    action_result="passed", assertion_result="passed")
    applicable = all(scope.get(k) == v for k, v in row["conditions"].items())
    restricted = any(all(scope.get(k) == v for k, v in rule.items()) for rule in row["paused_scopes"])
    if not applicable or restricted or paused or any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError("version has no current applicable unpaused source-case proof")


def restore(catalog, asset_id, version, scope, run_id, *, source_hash, expected_revision):
    """Restore an archived version within the already established active scope."""
    from .reusable_assets import inside, matches
    from .reuse_outcome import is_paused

    def apply(state):
        receipt, verified_result = committed_use(catalog.project,run_id,"passed")
        historical = state["versions"].get(asset_id, {}).get(str(version))
        active = state["assets"].get(asset_id)
        if not historical or not active or active["conditions"] != scope:
            raise ValueError("restoration would change an unverified scope")
        paused = catalog.paused(asset_id, version, scope) or is_paused(catalog.project, asset_id, version, scope)
        require_verified(asset_id, historical, scope, receipt, source_hash=source_hash, paused=paused)
        frozen = inside(catalog.project, historical["recovery_source"])
        if not frozen.is_file() or not matches(frozen, historical):
            raise ValueError("archived implementation unavailable")
        from .reusable_assets import _available, discover
        rows = discover(catalog.project, state=state)
        rows[asset_id] = dict(historical, status="available")
        _available(catalog.project, rows, asset_id, scope)  # Include live dependency decisions.
        state["assets"][asset_id] = dict(historical, conditions=dict(scope))
        state.setdefault("restores", []).append(dict(asset_id=asset_id, version=version, scope=dict(scope),
                                                    run_id=receipt["run_id"], source_hash=source_hash,
                                                    result_hash=verified_result))
    return catalog._commit(expected_revision, apply)
