"""阶段预算扩展的边界测试；所有写入均为本地夹具，不访问业务平台。"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from scripts.ui_test_core.case_contracts import canonical_hash,validate_document
from scripts.ui_test_core.execution_data_session import ExecutionDataSession,ExecutionDataError
from scripts.ui_test_core.stage_write_budget import (make_budget,validate_budget,validate_policies,select_stage_budget,check_phase_plan,StagePermitLedger,StageBudgetError,build_stage_qualification,validate_stage_qualification)
from scripts.ui_test_core.run_evidence_linker import build_run_result_v5,build_evidence_index_v2
from scripts.ui_test_core.finalization_transaction import FinalizationTransaction

H='sha256:'+'a'*64
CASE='CASE-STAGES'
BRANCH='main'
pytest_plugins=['pytester']

def budget(phases=None):
    return make_budget({'case_id':CASE,'branch_id':BRANCH,'phase_ids':phases or ['basic','detail','submit']})

def session(tmp_path,stage_budget):
    data={'schema_version':'ui-test.test-data.v2','case_id':CASE,'branch_id':BRANCH,'data_revision':1,'parameters':{'value':'fixture'},'generation_rules':{},'runtime_refs':[],'metadata':{}}
    path=tmp_path/'test-data.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data),encoding='utf-8')
    manifest={'case_id':CASE,'branch_id':BRANCH,'test_data_hash':canonical_hash(data),'parameters':[{'parameter_id':'value','ref':'test-data:/parameters/value','source_type':'test-data','value':'fixture'}]}
    manifest['parameter_manifest_hash']=canonical_hash(manifest)
    value=ExecutionDataSession(run_id='RUN-STAGES',build_fingerprint=H,test_data_path=path,parameter_manifest=manifest,stage_write_budget=stage_budget)
    value.start()
    value.seal_snapshot(tmp_path/'reports/resolved-test-data.json')
    return value

def run_result(tmp_path,value,stage_budget,*,passed=True):
    return build_run_result_v5(run_root=tmp_path,snapshot_path=tmp_path/'reports/resolved-test-data.json',transaction_id='FIN-STAGES',session_id='SESSION-STAGES',execution_context_ref='attempts/a/execution-context.json',execution_context_hash=H,attempt_ref='attempts/a',pre_terminal_events_hash=H,approval_ref='approval-record.json',approval_hash=H,run_id='RUN-STAGES',node_id='test_stage.py::test_case',case_id=CASE,branch_id=BRANCH,pytest_phase_status={'setup':'passed','call':'passed' if passed else 'failed','teardown':'passed'},overall_status='passed' if passed else 'failed',write_state='write_succeeded_verified' if passed else 'write_failed',submit_count=sum(r['submit_count'] for r in value.phase_results),stage_write_budget=stage_budget,phase_results=value.phase_results if stage_budget else None)

def test_default_stays_one_permit(tmp_path):
    value=session(tmp_path,None)
    permit=value.authorize_business_write()
    permit.consume()
    with pytest.raises(ExecutionDataError):permit.consume()
    with pytest.raises(StageBudgetError):value.authorize_business_write()

def test_explicit_three_stages_are_counted_and_committed(tmp_path):
    b=budget()
    value=session(tmp_path,b)
    for p in b['phase_ids']:
        value.authorize_business_write(p).consume()
        value.record_business_write_result(p,'write_succeeded_verified')
    result=run_result(tmp_path,value,b)
    assert result['submit_count']==3
    assert not validate_document(result,'run-result-v5.schema.json')
    evidence=build_evidence_index_v2(result,run_result_ref='objects/'+'0'*64+'.json')
    transaction=FinalizationTransaction(tmp_path)
    transaction.commit(transaction_id='FIN-STAGES',run_id='RUN-STAGES',node_id=result['node_id'],run_result=result,evidence_index=evidence)
    read=transaction.read_committed()
    assert read['run_result']['submit_count']==3
    assert read['evidence_index']['run_result_hash']==result['run_result_hash']

def test_unconfigured_count_two_is_rejected(tmp_path):
    value=session(tmp_path,None)
    value.authorize_business_write().consume()
    value.record_business_write_result(None,'write_succeeded_verified')
    result=run_result(tmp_path,value,None)
    result['submit_count']=2
    assert validate_document(result,'run-result-v5.schema.json')

@pytest.mark.parametrize('outcome',['write_failed','write_outcome_unknown','write_succeeded_verification_failed'])
def test_failed_or_unknown_stage_cannot_advance(tmp_path,outcome):
    value=session(tmp_path,budget())
    value.authorize_business_write('basic').consume()
    value.record_business_write_result('basic',outcome)
    with pytest.raises(StageBudgetError):
        value.record_business_write_result('basic', 'write_succeeded_verified')
    assert value.phase_results[0]['write_state'] == outcome
    with pytest.raises(StageBudgetError):value.authorize_business_write('detail')

@pytest.mark.parametrize('phase',['detail','submit','unlisted'])
def test_out_of_order_or_unlisted_stage_blocked(tmp_path,phase):
    value=session(tmp_path,budget())
    with pytest.raises(StageBudgetError):value.authorize_business_write(phase)
    assert sum(x['submit_count'] for x in value.phase_results)==0

def test_unused_issued_permit_is_not_counted_but_cannot_be_reissued(tmp_path):
    value=session(tmp_path,budget())
    value.authorize_business_write('basic')
    assert value.phase_results[0]['submit_count']==0
    with pytest.raises(StageBudgetError):value.authorize_business_write('basic')

def test_input_drift_before_second_stage_is_rejected(tmp_path):
    value=session(tmp_path,budget())
    value.authorize_business_write('basic').consume()
    value.record_business_write_result('basic','write_succeeded_verified')
    (tmp_path/'test-data.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ExecutionDataError,match='DRIFT'):value.authorize_business_write('detail')

def test_budget_tampering_is_rejected(tmp_path):
    value=session(tmp_path,budget())
    value.stage_write_budget['phase_ids'].append('extra')
    with pytest.raises(ExecutionDataError,match='BUDGET_DRIFT'):value.authorize_business_write('basic')

@pytest.mark.parametrize('kind',['sum','order','scope','hash','false-pass'])
def test_result_budget_invariants(tmp_path,kind):
    b=budget()
    value=session(tmp_path,b)
    value.authorize_business_write('basic').consume()
    value.record_business_write_result('basic','write_failed')
    result=run_result(tmp_path,value,b,passed=False)
    assert not validate_document(result,'run-result-v5.schema.json')
    if kind=='sum':result['submit_count']=2
    elif kind=='order':result['phase_results'].reverse()
    elif kind=='scope':result['case_id']='OTHER'
    elif kind=='hash':result['stage_write_budget']['budget_hash']=H
    else:
        result.update(overall_status='passed',write_state='write_succeeded_verified',pytest_phase_status={'setup':'passed','call':'passed','teardown':'passed'})
    assert validate_document(result,'run-result-v5.schema.json')

def test_policy_is_not_authorization_and_scope_is_exact():
    config={'schema_version':'2.3','scope':{'environment':'test'},'stage_write_policies':[{'case_id':CASE,'branch_id':BRANCH,'phase_ids':['basic','detail','submit']}]}
    assert select_stage_budget(config,CASE,BRANCH,'r2-ui-write-test')==budget()
    assert select_stage_budget(config,'OTHER',BRANCH,'r2-ui-write-test') is None
    with pytest.raises(StageBudgetError):select_stage_budget(config,CASE,BRANCH,'r1-read-only-authenticated')
    config['scope']['environment']='production'
    with pytest.raises(StageBudgetError):validate_policies(config)

def test_duplicate_policy_scope_is_invalid():
    p={'case_id':CASE,'branch_id':BRANCH,'phase_ids':['a']}
    with pytest.raises(StageBudgetError):validate_policies({'schema_version':'2.3','scope':{'environment':'test'},'stage_write_policies':[p,p]})

def steps():
    result=[]
    for p in ['basic','detail','submit']:
        result.extend([{'source_step_id':p+'-input','action':'fill'},{'source_step_id':p+'-save','action':'submit','parameters':[{'value':p}]}])
    return result

@pytest.mark.parametrize('index',[0,1,2])
def test_phase_qualification_never_claims_deferred_steps(tmp_path,index):
    s=steps()
    b=budget()
    screenshot=tmp_path/'screen.png'
    screenshot.write_bytes(b'unit-test-evidence')
    refs=[{'step_id':x['source_step_id'],'status':'passed'} for x in s[:index*2+1]]
    q=build_stage_qualification(run_id='RUN-Q',case_id=CASE,branch_id=BRANCH,build_fingerprint=H,budget=b,steps=s,step_results=refs,screenshot_ref='screen.png',screenshot_sha256='sha256:'+hashlib.sha256(screenshot.read_bytes()).hexdigest(),phase_index=index,prior_submit_count=index)
    assert q['deferred_phase_ids']==b['phase_ids'][index+1:]
    assert q['current_phase_submit_count']==0 and q['prior_submit_count']==index
    assert validate_stage_qualification(q,steps=s,budget=b,build_fingerprint=H,root=tmp_path)
    if index:
        with pytest.raises(StageBudgetError):validate_stage_qualification(q,steps=s,budget=b,build_fingerprint=H,root=tmp_path,activation=True)
    else:assert validate_stage_qualification(q,steps=s,budget=b,build_fingerprint=H,root=tmp_path,activation=True)
    q['deferred_phase_ids']=['undeclared']
    with pytest.raises(StageBudgetError):validate_stage_qualification(q,steps=s,budget=b,build_fingerprint=H,root=tmp_path)

def test_source_phase_plan_cannot_change_or_use_default_for_multiwrite():
    with pytest.raises(StageBudgetError):check_phase_plan(None,['a','b'],CASE,BRANCH)
    with pytest.raises(StageBudgetError):check_phase_plan(budget(),['detail','basic','submit'],CASE,BRANCH)

def test_pytest_plugin_binds_budget_without_granting_write(pytester):
    fixture_path=Path(__file__).with_name('test_pytest_runtime_plugin.py')
    spec=importlib.util.spec_from_file_location('stage_plugin_fixture',fixture_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text=module._V21_CONFIG_YAML+'\nstage_write_policies:\n  - case_id: CASE-STAGES\n    branch_id: main\n    phase_ids: [basic, detail, submit]\n'
    cfg=pytester.makefile('.yaml',project=text)
    pytester.makeconftest(module._PLUGIN_CONTEST+f'''
def pytest_ui_test_project_config_path():
    return r"{cfg}"
def pytest_addoption(parser):
    parser.addoption('--ui-pre-submit-only', action='store_true', default=False)
''')
    runner = pytester.makepyfile('''
import pytest
@pytest.mark.ui_test
@pytest.mark.case_id('CASE-STAGES')
@pytest.mark.branch_id('main')
@pytest.mark.r2
def test_case(ui_test_execution_context):
    ctx=ui_test_execution_context
    assert ctx.approved is False
    assert ctx.config_summary['stage_write_budget']['phase_ids']==['basic','detail','submit']
''')
    result=pytester.runpytest_subprocess(str(runner),'-q','--ui-run-id','RUN-STAGE-Q','--ui-pre-submit-only','--ui-execution-origin','codex-cli')
    result.assert_outcomes(passed=1)


def test_stage_qualification_rejects_drive_relative_path(tmp_path):
    b=budget()
    s=steps()
    q=build_stage_qualification(run_id='RUN-Q',case_id=CASE,branch_id=BRANCH,build_fingerprint=H,budget=b,steps=s,step_results=[{'step_id':'basic-input','status':'passed'}],screenshot_ref='C:outside.png',screenshot_sha256=H)
    with pytest.raises(StageBudgetError):
        validate_stage_qualification(q,steps=s,budget=b,build_fingerprint=H,root=tmp_path)

def test_failed_staged_pytest_has_failed_canonical_result_and_receipt(pytester):
    fixture_path=Path(__file__).with_name('test_pytest_runtime_plugin.py')
    spec=importlib.util.spec_from_file_location('stage_failure_fixture',fixture_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cfg=pytester.makefile('.yaml',project=module._V21_CONFIG_YAML+'\nstage_write_policies:\n  - case_id: CASE-STAGES\n    branch_id: main\n    phase_ids: [basic, detail, submit]\n')
    tests_dir=Path(__file__).parent
    root=pytester.path/'run'
    conftest=module._PLUGIN_CONTEST+f'''
import json
from pathlib import Path
from scripts.ui_test_core.case_contracts import canonical_hash
from scripts.ui_test_core.run_evidence_linker import build_run_result_v5,build_evidence_index_v2
def pytest_ui_test_project_config_path():
    return r"{cfg}"
def pytest_ui_test_finalization_target_v1(run_id,node_id,attempt_store):
    return {{'run_root':r"{root}"}}
def pytest_ui_test_build_finalization_candidate_v1(run_id,node_id,transaction_id,pre_terminal_events_hash,pytest_phase_status,attempt_store):
    ctx=attempt_store.read_execution_context(run_id=run_id,node_id=node_id)
    ref,digest=attempt_store.read_execution_context_ref_and_hash(run_id=run_id,node_id=node_id)
    root=Path(r"{root}")
    rows=json.loads((root/'pending.json').read_text())
    b=ctx['config_summary']['stage_write_budget']
    approval={{'schema_version':'ui-test.r2-approval-record.v3','approval_id':'APR-STAGES','approval_source':ctx['approval_source'],'run_id':run_id,'node_id':node_id,'case_id':ctx['case_id'],'branch_id':ctx['branch_id'],'environment':'test','allowed_action':ctx['branch_id'],'channel':'visible-ui','max_submit_count':3,'decision':'approved','credential_values_persisted':False,'reusable_across_runs':False,'risk_level':ctx['risk_level'],'runner_digest':ctx['runner_digest'],'stage_write_budget':b}}
    approval['boundary_hash']=canonical_hash({{k:approval[k] for k in ('run_id','case_id','environment','allowed_action','channel','max_submit_count')}})
    (root/'approval-record.json').write_text(json.dumps(approval))
    rr=build_run_result_v5(run_root=root,snapshot_path=root/'reports/resolved-test-data.json',transaction_id=transaction_id,session_id=ctx['session_id'],execution_context_ref=ref,execution_context_hash=digest,attempt_ref=ctx['attempt_ref'],pre_terminal_events_hash=pre_terminal_events_hash,approval_ref='approval-record.json',approval_hash=canonical_hash(approval),run_id=run_id,node_id=node_id,case_id=ctx['case_id'],branch_id=ctx['branch_id'],pytest_phase_status=dict(pytest_phase_status),overall_status='failed',write_state='write_failed',submit_count=1,stage_write_budget=b,phase_results=rows)
    return {{'run_result':rr,'evidence_index':build_evidence_index_v2(rr,run_result_ref='objects/'+'0'*64+'.json')}}
'''
    pytester.makeconftest(conftest)
    runner = pytester.makepyfile(f'''
import sys,json
from pathlib import Path
import pytest
sys.path.insert(0,r"{tests_dir}")
from test_stage_write_budget import session
@pytest.mark.ui_test
@pytest.mark.case_id('CASE-STAGES')
@pytest.mark.branch_id('main')
@pytest.mark.r2
def test_case(ui_test_execution_context):
    root=Path(r"{root}")
    value=session(root,ui_test_execution_context.config_summary['stage_write_budget'])
    value.authorize_business_write('basic').consume()
    value.record_business_write_result('basic','write_failed')
    (root/'pending.json').write_text(json.dumps(value.phase_results))
    assert False,'simulated business failure; no UI executed'
''')
    outcome=pytester.runpytest_subprocess(str(runner),'-q','--ui-run-id','RUN-STAGES','--ui-r2-approved','--ui-execution-origin','codex-cli')
    outcome.assert_outcomes(failed=1)
    committed=FinalizationTransaction(root).read_committed()
    assert committed['run_result']['overall_status']=='failed'
    assert committed['run_result']['submit_count']==1
    terminal=json.loads(next((pytester.path/'evidence/attempts').glob('*/terminal.json')).read_text())
    assert terminal['status']=='failed' and terminal['receipt_ref']
