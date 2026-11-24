const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');
const { fileURLToPath } = require('node:url');
const { runExplorationStage } = require('../skills/ui-test-explore/scripts/exploration_stage.cjs');

test('one exploration link retains the whole batch, its observations and stopping point', async (t) => {
  const outputRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'explore-test-'));
  t.after(() => fs.rmSync(outputRoot, { recursive: true, force: true }));
  const replay = path.join(outputRoot, 'native.html');
  fs.writeFileSync(replay, 'controlled replay');
  let calls = 0;
  const cases = [
    { id: 'A', run: async (record) => {
      calls++;
      record({ action: 'Inspect row', actual_result: 'Synthetic row is visible' });
    } },
    { id: 'B', run: async (record, stop) => {
      record({ action: 'Wait for dialog', actual_result: 'Still closed' });
      stop('Dialog remained closed at confirmation');
    } },
    { id: 'C', run: async () => { throw new Error('Unreachable'); } }
  ];
  const delivery = await runExplorationStage({ runId: 'test-33', outputRoot, cases, nativeReplay: replay });
  assert.equal(calls, 1);
  const html = fs.readFileSync(fileURLToPath(delivery.report_url), 'utf8');
  for (const expected of ['Midscene', 'Synthetic row is visible', 'Dialog remained closed at confirmation', 'not-executed'])
    assert.ok(html.includes(expected), expected);
  const raw = JSON.parse(fs.readFileSync(delivery.observations, 'utf8'));
  assert.deepEqual(raw.cases.map(item => item.status), ['observed', 'blocked', 'not-executed']);
  assert.equal(fileURLToPath(raw.cases[0].native_replay_url), replay);
  assert.equal(fileURLToPath(delivery.native_replay_url), replay);
  await assert.rejects(runExplorationStage({ runId: 'test-33', outputRoot, cases }), { code: 'EEXIST' });
  assert.equal(calls, 1);
});

test('archived observations retain attempts, stopped plan and missing evidence', async (t) => {
  const outputRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'explore-37-'));
  t.after(() => fs.rmSync(outputRoot, { recursive: true, force: true }));
  const calls = [];
  const cases = [
    {id:'query', attempt:'first', run(record) {
      calls.push('first');
      record({step_id:'row', action:'Check row A', status:'failed', expected_result:'approved', actual_result:'pending'});
    }},
    {id:'query', attempt:'second', run(record) {
      calls.push('second');
      record({step_id:'row', action:'Check row B', actual_result:'approved'});
    }},
    {id:'publish', plannedSteps:[{step_id:'open',action:'Open'},{step_id:'send',action:'Send'}], run(record, stop) {
      calls.push('third');
      record({step_id:'open',action:'Open',actual_result:'draft'});
      stop('Stopped before confirmation', 'send');
    }},
    {id:'later', run() { throw Error('unreachable'); }}
  ];
  const delivery = await runExplorationStage({runId:'controlled-37', outputRoot, cases});
  const archive = fs.readFileSync(delivery.observations);
  const html = fs.readFileSync(fileURLToPath(delivery.report_url), 'utf8');
  for (const fact of ['first','second','failed','pending','approved','最后记录的动作','无可审阅截图','未执行','Send','Stopped before confirmation'])
    assert.ok(html.includes(fact), fact);
  const bridge = path.resolve(__dirname, '../skills/ui-test-explore/scripts/publish_observations.py');
  const replay = require('node:child_process').spawnSync('python',['-X','utf8',bridge,'--archive',delivery.observations],{encoding:'utf8'});
  assert.equal(replay.status,0,replay.stderr);
  assert.equal(JSON.parse(replay.stdout).report_url,delivery.report_url);
  assert.deepEqual(fs.readFileSync(delivery.observations),archive);
  assert.deepEqual(calls,['first','second','third']);
  const altered = JSON.parse(archive);
  altered.cases[0].steps[0].images = [{attempt_ref:'second', missing_reason:'misbound fixture'}];
  const copyRoot = path.join(outputRoot,'conflicting','controlled-37');
  fs.mkdirSync(copyRoot,{recursive:true});
  const copy = path.join(copyRoot,'observations.json');
  fs.writeFileSync(copy,JSON.stringify(altered));
  const conflict = require('node:child_process').spawnSync('python',['-X','utf8',bridge,'--archive',copy],{encoding:'utf8'});
  assert.notEqual(conflict.status,0);
  assert.match(conflict.stderr,/E_STAGE_IMAGE_IDENTITY/);
  assert.equal(conflict.stdout,'');
  assert.equal(fs.existsSync(path.join(copyRoot,'report.html')),false);
  assert.equal(fs.readFileSync(delivery.report_html,'utf8'),html);
});
