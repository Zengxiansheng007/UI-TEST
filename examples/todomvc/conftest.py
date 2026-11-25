"""正式执行控制层由全局通用插件唯一拥有。"""
import sys
from pathlib import Path
import pytest
sys.dont_write_bytecode = True  # 全局包不得产生本轮缓存。
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / 'skills/ui-test/scripts'))
pytest_plugins = ('ui_test_core.pytest_runtime_plugin',)  # 所有正式节点显式加载唯一控制层。
from project_runtime import read, save, digest, paths, compiled, branch_root, attempt_root, PracticeRuntime
from ui_test_core.case_contracts import canonical_hash
from ui_test_core.reuse_outcome import reuse_verdict
from ui_test_core.release_verifier import verify_release
from ui_test_core.run_evidence_linker import build_run_result_v5, build_evidence_index_v2, verify_run_result_v5_links

def pytest_addoption(parser):
    parser.addoption('--ui-experience-trial', action='store_true', help='Validate a matching candidate under the normal case grant.')
    parser.addoption('--ui-pre-submit-only', action='store_true', default=False)  # 插件识别资格模式，不进入普通finalizer。
    parser.addoption('--ui-candidate-build', default=None)

def pytest_ui_test_project_config_path():
    return str(ROOT / 'ui-test.project.yaml')  # 使用当前工作树的项目配置。

def pytest_ui_test_execution_evidence_root():
    return str(ROOT / '运行' / '执行证据')

def pytest_ui_test_finalization_target_v1(run_id, node_id, attempt_store):
    context = attempt_store.read_execution_context(run_id=run_id, node_id=node_id)
    return {'run_root': str(attempt_root(context))}

def pytest_ui_test_build_finalization_candidate_v1(run_id, node_id, transaction_id, pre_terminal_events_hash, pytest_phase_status, attempt_store):
    context = attempt_store.read_execution_context(run_id=run_id, node_id=node_id)
    run_root = attempt_root(context)
    pending = read(run_root / 'pending.json')
    assert pending['context'] == context
    passed = all(value == 'passed' for value in pytest_phase_status.values())
    if passed:
        expected = compiled(context['case_id'], context['branch_id'])['resolved_ir']['resolved_steps']
        if [row['step_id'] for row in pending['steps']] != [step['source_step_id'] for step in expected]:
            raise ValueError('E_SOURCE_STEPS_INCOMPLETE')
        for row in pending['steps']:
            screenshot = 'reports/' + row['step_id'] + '.png'
            bound = screenshot in row['evidence_refs'] and (run_root / screenshot).is_file()
            missing = any(image.get('missing_reason') and image.get('step_id') == row['step_id']
                          and image.get('run_id') == run_id for image in row.get('images', []))
            if row['status'] != 'passed' or not (bound or missing):
                raise ValueError('E_SOURCE_STEP_EVIDENCE_INCOMPLETE')
    for step in pending['steps']:
        if step['step_id'] == 'COMPLETE' and 'strategy_use_ref' in step:
            relative = 'reports/script-use.json'
            linked = step['strategy_use_ref'] == relative and relative in step['evidence_refs']
            path = run_root / relative
            try:
                detail = read(path) if linked else None
            except (OSError, ValueError):
                detail = None
            verified = detail and canonical_hash(detail) == step.get('strategy_use_hash')
            step['reuse_verdict'] = reuse_verdict(detail if verified else None, context, 'COMPLETE')
            step['reuse_acceptance'] = step['reuse_verdict'] == 'verified'
            if not verified:
                step.pop('strategy_use_ref', None)
                step.pop('strategy_use_hash', None)
                step['evidence_refs'] = [ref for ref in step['evidence_refs'] if ref != relative]
        if step['step_id'] == 'OPEN':
            relative = 'reports/navigation-use.json'
            linked = relative in step['evidence_refs']
            path = run_root / relative
            detail = read(path) if linked and path.is_file() else None
            step['reuse_verdict'] = reuse_verdict(detail, context, 'OPEN')
            step['reuse_acceptance'] = step['reuse_verdict'] == 'verified'
            network_ref = 'reports/network-observation.json'
            if (run_root / network_ref).is_file():
                step['evidence_refs'].append(network_ref)
            if linked and detail is None:
                step['evidence_refs'].remove(relative)  # 缺失的明细不构成可交付证据。
    context_ref, context_hash = attempt_store.read_execution_context_ref_and_hash(run_id=run_id, node_id=node_id)
    evidence_refs = [ref for row in pending['steps'] for ref in row['evidence_refs']]
    artifact_index = run_root / 'playwright/artifacts.json'
    if artifact_index.is_file():  # Only link archived artifacts after their digests were recorded.
        evidence_refs.extend(entry['ref'] for entry in read(artifact_index))
        evidence_refs.append('playwright/artifacts.json')
    result = build_run_result_v5(run_root=run_root, snapshot_path=run_root / 'reports/resolved-test-data.json', transaction_id=transaction_id, session_id=context['session_id'], execution_context_ref=context_ref, execution_context_hash=context_hash, attempt_ref=context['attempt_ref'], pre_terminal_events_hash=pre_terminal_events_hash, approval_ref='approval-record.json', approval_hash=pending['approval_hash'], run_id=run_id, node_id=node_id, case_id=context['case_id'], branch_id=context['branch_id'], pytest_phase_status=dict(pytest_phase_status), overall_status='passed' if all(v == 'passed' for v in pytest_phase_status.values()) else 'failed', write_state=pending['write_state'], submit_count=pending['submit_count'], step_results=pending['steps'], evidence_refs=evidence_refs, cleanup_status='not_planned_this_release', stage_write_budget=context['config_summary'].get('stage_write_budget'), phase_results=pending['phase_results'] if context['config_summary'].get('stage_write_budget') else None)
    assert not verify_run_result_v5_links(result, run_root=run_root)
    return {'run_result': result, 'evidence_index': build_evidence_index_v2(result, run_result_ref='objects/' + '0' * 64 + '.json')}

@pytest.fixture(scope='session')
def browser_type_launch_args(browser_type_launch_args):
    return {**browser_type_launch_args, 'headless': False}

@pytest.fixture
def ui_test_runtime(ui_test_execution_context, new_context, request):
    return PracticeRuntime(ui_test_execution_context, new_context, request.config.getoption('--ui-pre-submit-only'),
                           request.config.getoption('--ui-experience-trial'))
