const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {runExplorationStage} = require(path.resolve(process.argv[2]));
async function verify() {
  const root = fs.mkdtempSync(path.join(process.argv[3],'runtime-project-'));
  if (process.argv[4] === 'duplicate') {
    fs.mkdirSync(path.join(root,'midscene','probe69'),{recursive:true});
    let calls = 0;
    await assert.rejects(runExplorationStage({outputRoot:root,runId:'probe69',cases:[{id:'c',run() {calls++;}}]}),{code:'EEXIST'});
    assert.equal(calls,0);
    process.stdout.write('Existing run; zero actions\n');
    return;
  }
  const cases = ['primary','second'].map(id => ({id, run(record) {
    record({step_id:'check',action:'Read '+id,actual_result:'Observed fixture '+id});
  }}));
  console.log = console.error;
  const delivery = await runExplorationStage({outputRoot:root,runId:'probe69',cases});
  const stage = JSON.parse(fs.readFileSync(delivery.stage_record));
  const evidence = JSON.parse(fs.readFileSync(delivery.step_evidence));
  const sql = "select stage_type, count(attempt_ref) from run_attempts group by stage_type";
  const rows = execFileSync('python',['-c','import sqlite3,sys,json; print(json.dumps(sqlite3.connect(sys.argv[1]).execute(sys.argv[2]).fetchall()))',path.join(root,'runs.sqlite3'),sql]);
  assert.deepEqual(JSON.parse(rows),[['midscene',2]]);
  assert.deepEqual(stage.cases.map(x=>x.case_id),['primary','second']);
  assert.deepEqual(evidence.steps.map(x=>[x.case_id,x.pointer]),[['primary','/cases/0/steps/0'],['second','/cases/1/steps/0']]);
  const html = fs.readFileSync(delivery.report_html,'utf8');
  assert.ok(html.includes('Observed fixture primary') && html.includes('Observed fixture second'));
  assert.deepEqual(fs.readdirSync(path.dirname(delivery.stage_record)).filter(x=>x.endsWith('.html')),['report.html']);
  process.stdout.write('Exploration cases=2, attempts=2, formal attempts=0, reports=1\n');
}
verify().catch(e=>{console.error(e);process.exitCode=1;});
