const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {execFileSync} = require('node:child_process');
const {runExplorationStage} = require('../scripts/exploration_stage.cjs');

test('reusing a recorded identity cannot replace an earlier observation', async t => {
  const root = fs.mkdtempSync(path.join(process.env.UI_TEST_PAUSE_EVIDENCE || os.tmpdir(), 'identity-'));
  if (!process.env.UI_TEST_PAUSE_EVIDENCE) t.after(() => fs.rmSync(root,{recursive:true,force:true}));
  const cases = [{id:'A',run(record) {
    record({step_id:'original',action:'Read label',actual_result:'First observed label'});
    record({step_id:'original',action:'Read label',actual_result:'A different label'});
  }}];
  await assert.rejects(runExplorationStage({outputRoot:root,runId:'identity',cases}), error => {
    assert.match(error.cause.message,/Conflicting recorded step identity/);
    const [row] = JSON.parse(fs.readFileSync(error.delivery.observations)).cases;
    assert.equal(row.steps.length,1);
    assert.equal(row.steps[0].actual_result,'First observed label');
    return true;
  });
});

test('unavailable window verification leaves the independent callback waiting', async t => {
  const root = fs.mkdtempSync(path.join(process.env.UI_TEST_PAUSE_EVIDENCE || os.tmpdir(),'window-'));
  if (!process.env.UI_TEST_PAUSE_EVIDENCE) t.after(() => fs.rmSync(root,{recursive:true,force:true}));
  let runs = 0;
  let screenshots = 0;
  const page = {context:() => ({browser:() => null}), frames:() => [], screenshot:() => {screenshots++;}};
  const cases = [{id:'A',usesStagePage:true,captureUnknown:false,async run(record,stop,capture,activePage) {
    assert.equal(activePage,page);
    const step = {step_id:'submit', action:'Submit'};
    await capture(activePage,step,{point:'unknown',object_ref:'fixture',observation:'Await receipt'});
    await capture(activePage,{...step,write_state:'unknown'},{point:'ordinary',object_ref:'fixture',observation:'Unconfirmed'});
  }},
    {id:'C',dependsOn:[],usesStagePage:true,run() {runs++;}}];
  const delivery = await runExplorationStage({runId:'waiting',outputRoot:root,page,cases});
  const [original,independent] = JSON.parse(fs.readFileSync(delivery.observations)).cases;
  assert.equal(runs,0);
  assert.equal(screenshots,0);
  assert.deepEqual(original.steps[0].images.map(img=>img.point),['unknown','ordinary']);
  for (const image of original.steps[0].images) {
    assert.match(image.missing_reason,/excluded by the case capture scope/);
    assert.equal(image.path,undefined);
  }
  const folder = path.dirname(delivery.observations);
  const events = fs.readdirSync(path.join(folder,'events')).filter(name => name.endsWith('.json'));
  assert.deepEqual(events.map(name => JSON.parse(fs.readFileSync(path.join(folder,'events',name))).identity[0]),['A']);
  assert.deepEqual(JSON.parse(fs.readFileSync(delivery.stage_record)).cases.find(c=>c.case_id==='C').attempts,[]);
  const counts = execFileSync('python', ['-c', [
    'import sqlite3,sys',
    'with sqlite3.connect(sys.argv[1]) as db:',
    ' print(db.execute("SELECT COUNT(*) FROM attempts WHERE case_id=?", ("C",)).fetchone()[0])',
  ].join('\n'),path.join(root,'runs.sqlite3')],{encoding:'utf8'});
  assert.equal(counts.trim(),'0');
  assert.equal(independent.status,'not-executed');
  assert.match(independent.reason,/verified separate browser window/);
});

test('one unknown write pauses its case and dependants; independent reads use a separate window', async t => {
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
  const browser = await chromium.launch({channel:'chromium',headless:process.env.UI_TEST_HEADED !== '1'});
  t.after(() => browser.close());
  const context = await browser.newContext();
  const original = await context.newPage();
  async function windowId(page) {
    const session = await context.newCDPSession(page);
    try {
      const {windowId} = await session.send('Browser.getWindowForTarget');
      assert.ok(Number.isInteger(windowId));
      return windowId;
    } finally { await session.detach(); }
  }
  const originalWindow = await windowId(original);
  let continuedWindow;
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
      assert.equal(page.context(),context);
      continuedWindow = await windowId(page);
      assert.notEqual(continuedWindow,originalWindow);
      assert.equal(page.url(),'about:blank');
      await page.goto(url);
      record({action:'Read title',actual_result:await page.locator('p').innerText()});
      freshReads++;
    }},
    {id:'record-only',dependsOn:[],usesStagePage:true,async run(record,stop,capture,page) {
      await page.goto(url);
      await page.getByText('Submit').click();
      record({step_id:'send',action:'Submit second fixture',actual_result:'No receipt',write_state:'write_unknown'});
    }},
    {id:'legacy-unbound',run() { throw new Error('Legacy callback reused'); }}
  ];
  const result = await runExplorationStage({runId:'unknown',outputRoot:root,page:original,cases});
  assert.equal(await original.locator('body').getAttribute('data-clicks'),'1');
  assert.equal(dependentRuns,0);
  assert.equal(freshReads,1);
  assert.equal(result.next_action,'review');
  const rows = JSON.parse(fs.readFileSync(result.observations)).cases;
  assert.deepEqual(rows.map(row=>row.status),['blocked','not-executed','observed','blocked','not-executed']);
  assert.match(rows[1].reason,/A/);
  assert.equal(rows[0].steps.length,1);
  assert.equal(rows[0].steps[0].step_id,'submit');
  assert.equal(rows[0].steps[0].write_state,'write_outcome_unknown');
  assert.deepEqual(rows[2].browser_window,{original_window_id:originalWindow,window_id:continuedWindow});
  assert.ok(fs.existsSync(rows[0].steps[0].images[0].path));
  assert.equal(rows[3].steps[0].images[0].point,'unknown');
  assert.ok(fs.existsSync(rows[3].steps[0].images[0].path));
  assert.match(rows[4].reason,/dependencies and a fresh stage page/);
});
