"""Read a scoped repair candidate and the original project evidence. Never dispatch a UI action."""
from pathlib import Path

from ui_test_core.suite import selected_suite

from .asset_repair import committed_record, impact_plan, repair_destination, require_verified


def _unknown_write(result):
    states = [result.get("write_state"), *(row.get("write_state") for row in result.get("phase_results", []))]
    return states[0] is None or "write_outcome_unknown" in states


def query(project=None, scope=None, authorization=None, asset_id=None, failure_run=None,
          source_cases=None, candidate_source=None, proof_project=None, proof_runs=None):
    """Describe the proposed file and optionally verify committed results for every affected case."""
    request = locals().copy()
    result = dict(status="pending-verification", scope=scope, stop_dependents=True,
                  business_attempts_added=0, activation_performed=False)
    missing = [key for key in ("project", "scope", "authorization", "asset_id", "failure_run", "source_cases")
               if not request[key]]
    if missing:
        return dict(result, missing=missing)
    assets = selected_suite().load_package("assets")
    files = assets.reusable_assets
    missing = [key for key in files.SELECTION_SCOPE if key not in scope or (key != "checkpoint" and not scope[key])]
    if missing:
        return dict(result, missing=missing)
    if authorization.get("scope") != scope or authorization.get("approved") is not True:
        return dict(result, reason="case_scope_not_authorized")
    root = Path(project).resolve()
    old, failed_result = committed_record(root, failure_run, "failed", asset_id=asset_id, step_id=scope["step_id"])
    if old.get("scope") != scope or old["case_id"] != scope["case_id"]:
        raise ValueError("failure scope differs from requested project or environment")
    evidence = dict(run_id=failure_run, attempt_ref=old["attempt_ref"], result_hash=failed_result["run_result_hash"],
                    asset_id=asset_id, version=old["version"], sha256=old["sha256"], source_hash=old["source_hash"])
    result.update(original=evidence, cause=old.get("failure", {}).get("cause", "unknown"))
    if _unknown_write(failed_result):
        return dict(result, reason="write_outcome_unknown")
    if result["cause"] != "asset":
        return dict(result, reason="asset_cause_unconfirmed")
    catalog, revision, rows = assets.repair_snapshot(root)
    row = rows.get(asset_id)
    if (not row or row["owner"] != {k: scope[k] for k in ("project_group", "product")}
            or any(scope.get(k) != v for k, v in row["conditions"].items())
            or row["sha256"] != old["sha256"] or row["version"] != old["version"]):
        return dict(result, reason="original_version_or_scope_changed")
    from ui_test_core.asset_revision import digest
    bindings = {case: item["bindings"] for case, item in source_cases.items()}
    impact = impact_plan(rows, asset_id, bindings)
    result.update(impact=impact, revision=revision)
    if impact["unresolved"] or scope["case_id"] not in impact["cases"]:
        return dict(result, reason="incomplete_impact")
    sources = {case: digest(files.inside(root, source_cases[case]["source"]).read_bytes()) for case in impact["cases"]}
    if sources[scope["case_id"]] != old["source_hash"]:
        return dict(result, reason="original_assertion_changed")
    if not candidate_source:
        return dict(result, missing=["candidate_source"])
    path = files.inside(root, candidate_source)
    sha = digest(path.read_bytes())
    if sha == row["sha256"] or not files.matches(path, dict(row, sha256=sha)):
        raise ValueError("candidate requires a changed implementation of the original symbol")
    candidate = dict(asset_id=asset_id, source=path.relative_to(root).as_posix(), sha256=sha,
                     version=row["version"] + 1, destination=repair_destination(row.get("source_ownership")),
                     original_sources=sources, scope=scope)
    result.update(candidate=candidate, status="candidate", pending_cases=impact["cases"])
    if not proof_runs or not proof_project:
        return result
    trial = Path(proof_project).resolve()
    verified = {}
    for case in impact["cases"]:
        if case not in proof_runs:
            continue
        expected_scope = dict(scope, case_id=case)
        proof, record = committed_record(trial, proof_runs[case], "passed", asset_id=asset_id, step_id=scope["step_id"])
        if _unknown_write(record):
            continue
        _, _, trial_rows = assets.repair_snapshot(trial)
        tested = trial_rows.get(asset_id, {})
        if (tested.get("owner") != row["owner"] or scope["step_id"] not in tested.get("steps", [])
                or tested.get("sha256") != sha or tested.get("version") != candidate["version"]
                or digest(files.inside(trial, source_cases[case]["source"]).read_bytes()) != sources[case]):
            raise ValueError("trial candidate or original assertion mismatch")
        assets.check_repair_candidate(trial, trial_rows, asset_id, expected_scope)
        require_verified(asset_id, tested, expected_scope, proof, source_hash=sources[case],
                         paused=(catalog.paused(asset_id, candidate["version"], expected_scope)
                                 or files.is_paused(root, asset_id, candidate["version"], expected_scope)))
        verified[case] = dict(run_id=proof_runs[case], result_hash=record["run_result_hash"])
    pending = sorted(set(impact["cases"]) - set(verified))
    if catalog.revision() != revision:
        raise ValueError("repair scope changed during verification")
    return dict(result, status="candidate" if pending else "verified-candidate",
                verification=verified, pending_cases=pending, stop_dependents=bool(pending))
