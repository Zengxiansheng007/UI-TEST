const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const suite = path.resolve(__dirname, '../../ui-test');
const resolve = name => JSON.parse(execFileSync('python', [
  path.join(suite,'scripts/ui_test_suite.py'),'--suite',suite,'resolve',name
])).skill;

test('both names deliver a single exploration with case-bound steps and no formal attempt', async t => {
  const canonical = resolve('explore');
  assert.equal(resolve('ui-test-explore'),canonical);
  for (const entry of [canonical, path.resolve(__dirname,'../../ui-test-explore')]) {
    const root = process.env.UI_TEST_69_EVIDENCE
      ? fs.mkdtempSync(path.join(process.env.UI_TEST_69_EVIDENCE,'project-'))
      : fs.mkdtempSync(path.join(os.tmpdir(),'explore-69-'));
    if (!process.env.UI_TEST_69_EVIDENCE) t.after(() => fs.rmSync(root,{recursive:true,force:true}));
    const {runExplorationStage} = require(path.join(entry,'scripts/exploration_stage.cjs'));
    const cases = ['read','inspect'].map(id => ({id,run(record) {
      record({step_id:'observe',action:'Inspect fixture',actual_result:'Controlled '+id});
    }}));
    const delivery = await runExplorationStage({runId:'standalone',outputRoot:root,cases});
    const stage = JSON.parse(fs.readFileSync(delivery.stage_record));
    assert.deepEqual(stage.cases.map(c=>[c.case_id,c.attempts.length]),[['read',1],['inspect',1]]);
    const proof = JSON.parse(fs.readFileSync(delivery.step_evidence));
    assert.deepEqual(proof.steps.map(s=>[s.case_id,s.pointer]),[['read','/cases/0/steps/0'],['inspect','/cases/1/steps/0']]);
    const runs = path.dirname(path.dirname(delivery.stage_record));
    assert.equal(fs.readdirSync(runs,{withFileTypes:true}).filter(entry=>entry.isDirectory()).length,1);
    assert.equal(stage.stage_type,'midscene');
    assert.equal(path.resolve(root,stage.report_ref),delivery.report_html);
    const html = fs.readFileSync(delivery.report_html,'utf8');
    assert.ok(html.includes('Controlled read') && html.includes('Controlled inspect'));
  }
});
