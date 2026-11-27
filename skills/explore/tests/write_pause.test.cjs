const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {runExplorationStage} = require('../scripts/exploration_stage.cjs');

test('one unknown write pauses its case and dependants; independent reads use a fresh page', async t => {
  const {chromium} = require(process.env.UI_TEST_PLAYWRIGHT || 'playwright');
  const root = fs.mkdtempSync(path.join(process.env.UI_TEST_PAUSE_EVIDENCE || os.tmpdir(), 'pause-'));
  if (!process.env.UI_TEST_PAUSE_EVIDENCE) t.after(() => fs.rmSync(root,{recursive:true,force:true}));
  const server = http.createServer((req,res) => {
    res.setHeader('Content-Type','text/html');
    res.end('<button onclick="document.body.dataset.clicks=+(document.body.dataset.clicks||0)+1">Submit</button><p>Fixture ready</p>');
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  t.after(() => server.close());
  const url = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch({headless:true});
  t.after(() => browser.close());
  const context = await browser.newContext();
  const original = await context.newPage();
  await original.goto(url);
  let dependentRuns = 0;
  let freshReads = 0;
  const cases = [
    {id:'A',run:async (record,stop,capture) => {
      const step = {step_id:'submit',action:'Submit fixture'};
      await original.getByText('Submit').click();
      await capture(original,step,{point:'unknown',object_ref:'fixture',observation:'No confirmation'});
      record({...step,write_state:'write_outcome_unknown'});
      await original.getByText('Submit').click();
    }},
    {id:'B',dependsOn:['A'],run() { dependentRuns++; }},
    {id:'C',dependsOn:[],usesStagePage:true,async run(record,stop,capture,page) {
      assert.notEqual(page,original);
      assert.equal(page.url(),'about:blank');
      await page.goto(url);
      record({action:'Read title',actual_result:await page.locator('p').innerText()});
      freshReads++;
    }}
  ];
  const result = await runExplorationStage({runId:'unknown',outputRoot:root,page:original,cases});
  assert.equal(await original.locator('body').getAttribute('data-clicks'),'1');
  assert.equal(dependentRuns,0);
  assert.equal(freshReads,1);
  assert.equal(result.next_action,'review');
  const rows = JSON.parse(fs.readFileSync(result.observations)).cases;
  assert.deepEqual(rows.map(row=>row.status),['blocked','not-executed','observed']);
  assert.match(rows[1].reason,/A/);
  assert.equal(rows[0].steps.length,1);
  assert.equal(rows[0].steps[0].step_id,'submit');
  assert.equal(rows[0].steps[0].write_state,'write_outcome_unknown');
  assert.ok(fs.existsSync(rows[0].steps[0].images[0].path));
});
