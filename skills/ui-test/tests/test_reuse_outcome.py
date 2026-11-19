import pytest

from ui_test_core.reuse_outcome import ReuseFailure, failure_outcome, reuse_verdict


CONTEXT = {'run_id': 'R1', 'case_id': 'C1', 'attempt_ref': 'attempts/1.json'}
USE = dict(CONTEXT, step_id='OPEN', asset_id='shared', version=1, environment='test', selected=True, entered=False)


@pytest.mark.parametrize('cause', ['business', 'environment', 'data', 'unknown'])
def test_non_asset_failure_keeps_shared_version_available(cause):
    outcome = failure_outcome(ReuseFailure(cause, 'precondition_failed'), USE)
    assert outcome == dict(cause=cause, reason='precondition_failed', pause_scope=None, stop_dependents=True)
    assert reuse_verdict(USE, CONTEXT, 'OPEN') == 'unproven'


def test_asset_failure_targets_one_version_and_use():
    outcome = failure_outcome(ReuseFailure('asset', 'symbol_missing'), USE)
    assert outcome['pause_scope'] == dict(asset_id='shared', version=1, case_id='C1', step_id='OPEN', environment='test')
    assert failure_outcome(TimeoutError(), USE)['cause'] == 'unknown'


def test_confirmed_asset_failure_without_environment_stops_without_pausing():
    use = USE.copy()
    del use['environment']
    outcome = failure_outcome(ReuseFailure('asset', 'symbol_missing'), use)
    assert outcome['cause'] == 'asset'
    assert outcome['stop_dependents'] is True
    assert outcome['pause_scope'] is None


def test_verify_only_same_attempt_with_action_and_assertion():
    detail = dict(USE, entered=True, action_result='passed', assertion_result='passed')
    assert reuse_verdict(detail, CONTEXT, 'OPEN') == 'verified'
    for incomplete in (None, USE, dict(detail, attempt_ref='other'), dict(detail, assertion_result=None)):
        assert reuse_verdict(incomplete, CONTEXT, 'OPEN') == 'unproven'
