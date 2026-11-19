from scripts.ui_test_core.reuse_outcome import ReuseFailure, failure_outcome, is_paused, persist_pause, reuse_verdict


def test_only_confirmed_asset_pauses_exact_version_and_scope(tmp_path):
    scope = dict(case_id="A", step_id="OPEN", environment="test")
    use = dict(asset_id="nav", version=1, run_id="run", **scope)
    for cause in ("environment", "business", "data", "unknown", "asset"):
        failure = failure_outcome(ReuseFailure(cause, "observed"), use)
        persist_pause(tmp_path, failure)
        assert failure["cause"] == cause and failure["stop_dependents"]
        assert is_paused(tmp_path, "nav", 1, scope) == (cause == "asset")
    assert not is_paused(tmp_path, "nav", 2, scope)
    assert not is_paused(tmp_path, "nav", 1, dict(scope, case_id="B"))


def test_missing_detail_and_unentered_selection_are_distinct():
    context = dict(run_id="r", attempt_ref="a", case_id="c")
    use = dict(context, step_id="OPEN", asset_id="nav", version=1,
               selected=True, discovered=True, entered=False)
    assert reuse_verdict(None, context, "OPEN") == "unproven"
    assert reuse_verdict(use, context, "OPEN") == "selected_not_entered"
    assert reuse_verdict(dict(use, run_id="older"), context, "OPEN") == "unproven"
