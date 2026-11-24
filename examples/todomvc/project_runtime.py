"""练习项目运行时仅消费插件上下文并返回候选。"""
import hashlib
import json
from urllib.parse import urlsplit
from pathlib import Path
from dataclasses import asdict
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from ui_test_core.case_contracts import canonical_hash, validate_document
from window_observation import observe_window
from ui_test_core.stage_capture import STANDARD_MASK, capture_step
from ui_test_core.execution_data_session import ExecutionDataSession
from ui_test_core.execution_parameter_guard import ExecutionParameterGuard
from ui_test_core.failure_repair_store import FailureRepairEventStore
from ui_test_core.stage_write_budget import build_stage_qualification, validate_stage_qualification
from ui_test_core.reusable_assets import check_selected_pauses, inside, select_asset
from ui_test_core.asset_revision import AssetCatalog, deliver_event
from ui_test_core.reuse_outcome import ReuseFailure, failure_outcome, persist_pause
from ui_test_core.strategy_learning import applicable_experiences, choose_strategy

ROOT = Path(__file__).resolve().parent

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))  # 读取本任务已封存材料。

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as temp:
        json.dump(value, temp, ensure_ascii=False, indent=2)
    Path(temp.name).replace(path)

def digest(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()

def paths(case_id):
    return read(ROOT / 'asset-paths.json')[case_id]

def compiled(case_id):
    return read(ROOT / 'compiled' / (case_id + '.json'))

def branch_root(case_id):
    return ROOT / paths(case_id)['branch_root']


def verify_counter_action(action, todo, text, expected_count, checked):
    try:
        return action()
    except AssertionError as error:
        # A count mismatch is attributable only when the intended row and checkbox state independently match.
        if (todo.rows.count() == 1 and todo.rows.get_by_text(text, exact=True).count() == 1
                and todo.rows.get_by_role('checkbox').count() == 1
                and todo.rows.get_by_role('checkbox').is_checked() == checked
                and todo.counter.count() == 1 and todo.counter.is_visible()
                and todo.counter.inner_text().strip() != expected_count):
            raise ReuseFailure('business', 'visible_remaining_count_mismatch') from error
        raise

class PracticeRuntime:
    def __init__(self, context, new_context, qualification, experience_trial=False):
        self.context = asdict(context)  # 插件是上下文及run ID唯一来源。
        self.new_context = new_context
        self.qualification = qualification
        self.experience_trial = experience_trial

    def execute_case(self, *, case_id, branch_id, parameter_manifest, step_manifest):
        c = self.context
        assert (case_id, branch_id) == (c['case_id'], c['branch_id'])
        assert c['approved'] and c['environment'] == 'test' and c['risk_level'] == 'r2-ui-write-test'
        frozen = compiled(case_id)
        assert parameter_manifest == frozen['parameter_manifest'] and step_manifest == frozen['resolved_ir']['resolved_steps']
        budget = c['config_summary'].get('stage_write_budget')
        run_root = branch_root(case_id) / 'runs' / c['run_id']
        output = run_root / 'qualification' if self.qualification else run_root / 'reports'
        output.mkdir(parents=True, exist_ok=True)
        if not self.qualification:
            if (run_root / 'pending.json').exists() or (run_root / 'approval-record.json').exists():
                raise RuntimeError('E_EXISTING_RUN_REQUIRES_RECEIPT_RECOVERY')
            (run_root / 'execution-started').touch(exist_ok=False)  # 重送或并发运行不得覆盖原账本。
        session = ExecutionDataSession(run_id=c['run_id'], build_fingerprint=frozen['manifest']['build_fingerprint'], test_data_path=branch_root(case_id) / 'tests/test-data.json', parameter_manifest=parameter_manifest, stage_write_budget=budget)
        store = FailureRepairEventStore(ROOT / 'diagnostics', product_id='todomvc')
        guard = ExecutionParameterGuard(session, store, source_file_ref='tests/test-data.json')
        guard.start()  # 参数漂移必须在BrowserContext前阻断。
        browser_context = self.new_context(viewport={'width': 1360, 'height': 900})
        actions = []
        def observed_action(kind):
            if kind in ('submit-enter', 'checkbox-change'):
                actions.append(kind)  # 不接受来自页面的任意字符串或输入值。
        browser_context.expose_function('__todoObservedAction', observed_action)
        browser_context.add_init_script("""(() => {
            document.addEventListener('keydown', event => {
                if (event.isTrusted && event.key === 'Enter' && event.target.matches('.new-todo'))
                    window.__todoObservedAction('submit-enter');
            }, true);
            document.addEventListener('change', event => {
                if (event.isTrusted && event.target.matches('.todo-list input[type=checkbox]'))
                    window.__todoObservedAction('checkbox-change');
            }, true);
        })()""")
        page = browser_context.new_page()
        page.set_default_timeout(15000)
        def reviewed(request):
            address = urlsplit(request.url)
            resources = {'/todomvc/', '/todomvc/base.css', '/todomvc/index.css',
                         '/todomvc/js/director.js', '/todomvc/js/bundle.js'}
            return (address.scheme == 'https' and address.netloc == 'demo.playwright.dev'
                    and address.path in resources and not address.query and request.method == 'GET')
        page.route('**/*', lambda route: route.continue_() if reviewed(route.request) else route.abort())
        network = []
        def observe(request, status=None):
            if reviewed(request):
                network.append(dict(method=request.method, resource_type=request.resource_type,
                                    path_hash=hashlib.sha256(urlsplit(request.url).path.encode()).hexdigest(),
                                    status=status))
        page.on('request', lambda request: observe(request))
        page.on('response', lambda response: observe(response.request, response.status))
        rows = []
        selection_refs = {}
        catalog = AssetCatalog(ROOT)
        revision, pinned_rows = catalog.pin()  # 一次用例从同一份清单选择全部步骤及依赖。

        def record_event(sid, sequence, **payload):
            event = dict(run_id=c['run_id'], attempt_ref=c['attempt_ref'], step_id=sid,
                         sequence=sequence, revision=revision, **payload)
            if deliver_event(output / 'use-events', event) == 'conflict':
                raise ReuseFailure('unknown', 'conflicting_step_event')

        def check_pause(sid, selected):
            scope = dict(selected['scope'], step_id=sid)
            check_selected_pauses(ROOT, selected, pinned_rows, scope)

        def resolve_step(sid, capability, effects, *, binding=None, explore=False, early=False):
            step = next(item for item in step_manifest if item['source_step_id'] == sid)
            scope = dict(frozen['case_ir']['scope'], checkpoint=step.get('checkpoint'), environment=c['environment'],
                         risk_level=c['risk_level'], case_id=case_id, step_id=sid)
            facts = ['page_available', *(row['step_id'] for row in rows if row['status'] == 'passed')]
            grant = dict(scope=scope, approved=c['approved'], effects=effects, facts=facts, explore=explore,
                         exploration_effect='read' if explore else None)
            if binding is None and step['binding_ref'] != 'page.todomvc':
                binding = step['binding_ref']  # The page binding delegates its component implementation.
            decision = select_asset(ROOT, capability, scope, grant, binding=binding, pinned_rows=pinned_rows)
            if early and decision['status'] != 'selected':
                return None  # Re-evaluate at the step once its prerequisites are observable.
            decision['catalog_revision'] = revision
            receipt = output / (sid + '-selection.json')
            save(receipt, dict(run_id=c['run_id'], attempt_ref=c['attempt_ref'], selection=decision))
            selection_refs[sid] = [receipt.relative_to(run_root).as_posix()]
            record_event(sid, 0, status=decision['status'], selection_ref=selection_refs[sid][0],
                         selection_hash=canonical_hash(decision))
            if decision['status'] not in ('selected', 'exploration_allowed'):
                raise ReuseFailure('unknown', sid + ': ' + decision['reason'])
            return decision

        failed_use = {}

        def load_page_asset(key, scope, expected_kind, method, asset=None):
            asset = pinned_rows[key] if asset is None else asset
            source = inside(ROOT, asset['recovery_source'])
            implementation = source.read_bytes()
            if hashlib.sha256(implementation).hexdigest() != asset['sha256']:
                raise ValueError('E_ASSET_VERSION_UNAVAILABLE')
            owner, _, symbol = asset['symbol'].rpartition('.')
            if not owner.isidentifier() or symbol != method or asset['kind'] != expected_kind:
                failed_use.update(scope, asset_id=key, version=asset['version'])
                raise ReuseFailure('asset', 'asset_entry_contract_mismatch')
            module = {'__name__': 'todomvc_page', '__file__': str(source)}
            exec(compile(implementation, str(source), 'exec'), module)
            instance = module[owner](page)
            for key in asset['dependencies']:
                dependency = pinned_rows[key]
                if dependency['kind'] != 'locator':
                    raise ReuseFailure('unknown', 'unsupported_page_dependency')
                cls, initializer, attr = dependency['symbol'].split('.')
                if initializer != '__init__' or not attr.isidentifier():
                    raise ReuseFailure('unknown', 'unsupported_locator_symbol')
                descriptor = dict(dependency, symbol=cls + '.__init__')
                provider = load_page_asset(key, scope, 'locator', initializer, descriptor)
                setattr(instance, attr, getattr(provider, attr))
            return instance

        def evidence(sid, point, object_ref, observation):
            target = output / (sid + '.png')
            row = {'step_id': sid, 'status': 'passed', 'evidence_refs': []}
            capture_step(page, row, context=c, run_root=run_root, point=point, object_ref=object_ref,
                         observation=observation, ref=target.relative_to(run_root))
            row['evidence_refs'].extend(selection_refs.get(sid, ()))
            rows.append(row)
            record_event(sid, 1, status='passed', evidence_refs=row['evidence_refs'])
            return target
        def qualification(index):
            screen = output / (f'boundary-{index}.png')
            page.screenshot(path=str(screen), mask=[page.locator(STANDARD_MASK)], mask_color='#000000')
            if budget:
                result = build_stage_qualification(run_id=c['run_id'], case_id=case_id, branch_id=branch_id, build_fingerprint=frozen['manifest']['build_fingerprint'], budget=budget, steps=step_manifest, step_results=rows, screenshot_ref=screen.relative_to(run_root).as_posix(), screenshot_sha256=digest(screen), phase_index=index, prior_submit_count=index)
                validate_stage_qualification(result, steps=step_manifest, budget=budget, build_fingerprint=frozen['manifest']['build_fingerprint'], root=run_root, activation=index == 0)
            else:
                result = {'schema_version': 'ui-test.pre-submit-qualification-result.v1', 'run_id': c['run_id'], 'case_id': case_id, 'branch_id': branch_id, 'build_fingerprint': frozen['manifest']['build_fingerprint'], 'overall_status': 'passed', 'step_results': list(rows), 'screenshot_ref': screen.relative_to(run_root).as_posix(), 'screenshot_sha256': digest(screen), 'submit_count': 0, 'write_state': 'not_attempted', 'sequence_allocated': False}
                assert not validate_document(result, 'pre-submit-qualification-result.schema.json')
            save(output / (f'qualification-{index}.json'), result)
            return result
        def dispatch(phase):
            permit = session.authorize_business_write(phase)  # 核对封存输入后才允许占用预算。
            marker = run_root / ('dispatched-' + (phase or 'single') + '.json')
            with marker.open('x', encoding='utf-8') as handle:  # 同一运行重入时拒绝重复提交。
                json.dump({'phase': phase, 'write_state': 'write_outcome_unknown'}, handle)
            permit.consume()
            capture_write_progress()  # 在 UI 派发前保留本次已消耗的预算。

        def capture_write_progress():
            phases = session.phase_results
            attempted = [row for row in phases if row['submit_count']]
            pending = {'context': c, 'steps': rows, 'phase_results': phases,
                       'write_state': attempted[-1]['write_state'] if attempted else 'not_attempted',
                       'submit_count': sum(row['submit_count'] for row in phases),
                       'approval_hash': canonical_hash(approval)}
            target = run_root / 'pending.json'
            save(target, pending)

        if not self.qualification:
            approval = {'schema_version': 'ui-test.r2-approval-record.v3', 'approval_id': 'APPROVAL-' + c['run_id'], 'approval_source': c['approval_source'], 'run_id': c['run_id'], 'node_id': c['node_id'], 'case_id': case_id, 'branch_id': branch_id, 'environment': 'test', 'allowed_action': 'public-todomvc-visible-ui', 'channel': 'visible-ui', 'max_submit_count': len(budget['phase_ids']) if budget else 1, 'decision': 'approved', 'credential_values_persisted': False, 'reusable_across_runs': False, 'risk_level': c['risk_level'], 'runner_digest': c['runner_digest']}
            boundary_fields = ('run_id', 'case_id', 'environment', 'allowed_action', 'channel', 'max_submit_count')
            approval['boundary_hash'] = canonical_hash({key: approval[key] for key in boundary_fields})
            if budget:
                approval['stage_write_budget'] = budget
            assert not validate_document(approval, 'r2-approval-record-v3.schema.json')
            save(run_root / 'approval-record.json', approval)
        try:
            step = next(item for item in step_manifest if item['source_step_id'] == 'OPEN')
            decision = resolve_step('OPEN', 'flow.open-todomvc', ['read', 'navigation'], binding=step['binding_ref'])
            asset = decision['asset']
            detail = dict(run_id=c['run_id'], attempt_ref=c['attempt_ref'], asset_id=decision['asset_id'],
                          **decision['scope'], **asset, discovered=True, selected=True, entered=False)
            detail_path = output / 'navigation-use.json'
            save(detail_path, detail)
            ready = resolve_step('READY-COMPLETE', 'component.ready', ['read'], explore=True, early=True) if budget else None
            check_pause('OPEN', decision)
            todo = load_page_asset(decision['asset_id'], decision['scope'], 'navigation', 'open')
            def entered(current_page):
                if current_page is not page or current_page.context is not browser_context:
                    raise RuntimeError('E_NAVIGATION_CONTEXT_CHANGED')
                detail['entered'] = True
                save(detail_path, detail)

            from playwright.sync_api import expect
            check_pause('OPEN', decision)
            try:
                todo.open(guard.consume('base-url'), on_entry=entered)
            except Exception as navigation_error:
                if detail['entered'] and page.get_by_text('Session expired', exact=True).is_visible():
                    raise ReuseFailure('environment', 'session_expired') from navigation_error
                raise
            if page.get_by_text('Session expired', exact=True).is_visible():
                raise ReuseFailure('environment', 'session_expired')
            expect(page.get_by_placeholder('What needs to be done?')).to_be_visible()
            expect(page.locator('.todo-list li')).to_have_count(0)
            detail.update(action_result='passed', assertion_result='passed',
                          input_visible=todo.input.is_visible(), row_count=todo.rows.count())
            save(detail_path, detail)
            save(output / 'window-observation.json', observe_window(page))
            evidence('OPEN', 'ordinary', 'Todo list', 'New todo input visible and list empty')
            rows[-1]['evidence_refs'].append(detail_path.relative_to(run_root).as_posix())
            check_pause('FILL', decision)
            todo.fill(guard.consume('text'))
            evidence('FILL', 'pre_submit', todo.input.input_value(), 'Input contains the verified case title')
            first_q = qualification(0)  # 仅证明第一写入前边界，后续阶段仍待核验。
            session.seal_snapshot(output / 'resolved-test-data.json')
            if self.qualification:
                save(ROOT / 'qualifications' / (case_id + '.json'), {'run_root': str(run_root), 'result': first_q})
                return
            text, empty, added = (guard.consume(key) for key in ('text', 'empty', 'count_added'))
            check_pause('ADD', decision)
            dispatch('add' if budget else None)
            verify_counter_action(lambda: todo.add(text, empty, added), todo, text, added, False)
            session.record_business_write_result('add' if budget else None, 'write_succeeded_verified')
            evidence('ADD', 'final', text, 'Target row visible, input cleared, remaining count ' + added)
            if budget:
                ready = ready or resolve_step('READY-COMPLETE', 'component.ready', ['read'], explore=True)
                if ready['status'] == 'selected':
                    check_pause('READY-COMPLETE', ready)
                    load_page_asset(ready['asset_id'], ready['scope'], 'component', 'ready_complete').ready_complete()
                else:
                    # Independently inspect the source step's row and checkbox using the current page.
                    exploration = output / 'READY-COMPLETE-exploration.json'
                    record = dict(run_id=c['run_id'], attempt_ref=c['attempt_ref'], scope=ready['scope'],
                                  reason=ready['reason'], action='inspect current todo row', status='started')
                    save(exploration, record)
                    selection_refs['READY-COMPLETE'].append(exploration.relative_to(run_root).as_posix())
                current_rows = page.locator('.todo-list li')
                expect(current_rows).to_have_count(1)
                expect(current_rows.get_by_text(text, exact=True)).to_have_count(1)
                expect(current_rows.get_by_role('checkbox')).not_to_be_checked()
                if ready['status'] == 'exploration_allowed':
                    save(exploration, dict(record, status='passed'))
                evidence('READY-COMPLETE', 'pre_submit', text, 'Unique matching target row is unchecked')
                qualification(1)  # 同一context核对第二写入前的完整已执行前缀。
                completed = guard.consume('count_completed')
                choice = resolve_step('COMPLETE', 'script.complete', ['read', 'UI write'])
                asset = choice['asset']
                if (asset.get('inputs') != ['page', 'counter'] or asset.get('action') != 'check-target-checkbox'
                        or asset.get('side_effects') != 'UI write'):
                    raise ReuseFailure('unknown', 'legacy_script_contract_unreviewed')
                check_pause('COMPLETE', choice)
                completion = load_page_asset(choice['asset_id'], choice['scope'], 'script', 'complete')
                assert completion.page is page and page.context is browser_context
                identity = dict(asset_id=choice['asset_id'], **{k: asset[k] for k in ('version', 'sha256', 'symbol')})
                build = frozen['manifest']['build_fingerprint']
                matches = applicable_experiences(ROOT, choice['scope'], identity, build, trial=self.experience_trial)
                strategies = ('verify-unique-source-row-before-completing', 'scope-to-exact-source-row')
                strategy, uses = choose_strategy(strategies, matches)
                script_ref = 'reports/script-use.json'
                script_path = run_root / script_ref
                script = dict(run_id=c['run_id'], case_id=case_id, step_id='COMPLETE', attempt_ref=c['attempt_ref'],
                              scope=choice['scope'], asset=identity, **identity, build=build, discovered=True,
                              selected=True, entered=False, strategy=strategy, experiences=uses,
                              condition='unique unchecked row matching the source input', action=asset['action'],
                              expected=dict(checked=True, remaining=completed),
                              actual=dict(remaining_before=todo.counter.inner_text(), initial_script_rows=completion.rows.count()),
                              action_result='pending', assertion_result='unverified')
                selection_refs['COMPLETE'].append(script_ref)
                save(script_path, script)
                if strategy is None:
                    script.update(action_result='skipped', reason='all_reviewed_strategies_excluded')
                    save(script_path, script)
                    raise ReuseFailure('unknown', script['reason'])
                if strategy == 'scope-to-exact-source-row':
                    completion.rows = current_rows.filter(has=page.get_by_text(text, exact=True))
                    expect(completion.rows).to_have_count(1)
                if uses:
                    expect(current_rows.get_by_text(text, exact=True)).to_have_count(1)
                    expect(current_rows.get_by_role('checkbox')).not_to_be_checked()
                check_pause('COMPLETE', choice)
                dispatch('complete')
                def invoke_script():
                    try:
                        completion.complete(completed)
                    except Exception as error:
                        import traceback
                        script['entered'] = any(frame.f_code is completion.complete.__code__
                                                for frame, _ in traceback.walk_tb(error.__traceback__))
                        script.update(action_result='unknown', assertion_result='failed' if isinstance(error, AssertionError) else 'unverified')
                        script['actual']['failure_type'] = type(error).__name__
                        save(script_path, script)
                        raise
                    script.update(entered=True, action_result='passed')
                    save(script_path, script)
                verify_counter_action(invoke_script, completion, text, completed, True)
                expect(current_rows.get_by_role('checkbox')).to_be_checked()
                expect(page.locator('.todo-count')).to_have_text(completed)
                expect(page.get_by_role('button', name='Clear completed')).to_be_visible()
                script['actual'].update(checked=current_rows.get_by_role('checkbox').is_checked(),
                                        remaining_after=todo.counter.inner_text(), clear_visible=True)
                script['assertion_result'] = 'passed'
                save(script_path, script)
                session.record_business_write_result('complete', 'write_succeeded_verified')
                evidence('COMPLETE', 'final', text, 'Target checked, clear control visible, remaining count ' + completed)
                rows[-1].update(strategy_use_ref=script_ref, strategy_use_hash=canonical_hash(script),
                                reuse_verdict='verified', reuse_acceptance=True)
            save(run_root / 'pending.json', {'context': c, 'steps': rows, 'phase_results': session.phase_results, 'write_state': 'write_succeeded_verified', 'submit_count': sum(row['submit_count'] for row in session.phase_results), 'approval_hash': canonical_hash(approval), 'scope_crosswalk': {'tca_module_path': read(ROOT / 'authoring-module-paths.json')[case_id], 'formal_scope': frozen['case_ir']['scope']}, 'tca_tested_version': {'semantic_version': paths(case_id)['semantic_version'], 'data_version': paths(case_id)['data_version']}, 'formal_build_fingerprint': frozen['manifest']['build_fingerprint']})
        except Exception as error:
            if not self.qualification:
                if session.snapshot_ref is None:
                    session.seal_snapshot(output / 'resolved-test-data.json')
                use = locals().get('detail', {}) if not rows else {}
                failure = failure_outcome(error, failed_use)
                persist_pause(ROOT, failure)
                if use:
                    use.update(action_result='failed' if use['entered'] else 'skipped',
                               assertion_result='unverified', reason=failure['reason'])
                    save(detail_path, use)
                done = {row['step_id'] for row in rows}
                remaining = [step['source_step_id'] for step in step_manifest if step['source_step_id'] not in done]
                for index, sid in enumerate(remaining):
                    record_event(sid, 2, status='failed' if index == 0 else 'skipped',
                                 reason=failure['reason'] if index == 0 else 'predecessor_failed')
                    rows.append({'step_id': sid, 'status': 'failed' if index == 0 else 'skipped',
                                 'reason': failure['reason'] if index == 0 else 'predecessor_failed',
                                 'failure': failure, 'evidence_refs': list(selection_refs.get(sid, ()))})
                    if index == 0:
                        point = 'timeout' if isinstance(error, (PlaywrightTimeoutError, TimeoutError)) else 'failure'
                        capture_step(page, rows[-1], context=c, run_root=run_root, point=point,
                                     object_ref=sid, observation='Execution stopped: ' + failure['reason'],
                                     ref='reports/failure.png')
                    if sid == 'OPEN' and use:
                        rows[-1]['evidence_refs'].append(detail_path.relative_to(run_root).as_posix())
                    if sid == 'READY-COMPLETE' and index > 0 and locals().get('ready') and ready['status'] == 'selected':
                        record = dict(ready['scope'], run_id=c['run_id'], attempt_ref=c['attempt_ref'],
                                      asset_id=ready['asset_id'], version=ready['asset']['version'],
                                      sha256=ready['asset']['sha256'], discovered=True, selected=True, entered=False,
                                      reason='predecessor_failed', action_result='skipped', assertion_result='unverified')
                        skipped = output / 'READY-COMPLETE-skipped.json'
                        save(skipped, record)
                        rows[-1]['evidence_refs'].append(skipped.relative_to(run_root).as_posix())
                        rows[-1].update(reuse_verdict='selected_not_entered', reuse_acceptance=False)
                    if sid == 'COMPLETE' and 'script' in locals():
                        rows[-1].update(strategy_use_ref=script_ref, strategy_use_hash=canonical_hash(script))
                capture_write_progress()  # 截图失败也不丢失已占预算。
            if self.qualification:
                page.screenshot(path=str(output / 'failure.png'), mask=[page.locator(STANDARD_MASK)], mask_color='#000000')
            raise
        finally:
            try:
                save(output / 'network-observation.json', {'events': network, 'ui_actions': actions})
            finally:
                browser_context.close()
