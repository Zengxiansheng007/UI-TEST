const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { runExplorationStage } = require('../skills/ui-test-explore/scripts/exploration_stage.cjs');

test('live observation captures each write boundary and the asserted target in masked original pixels', async () => {
  const { chromium } = require(process.env.CHECKPOINT_RUNTIME_PLAYWRIGHT_MODULE || 'D:/midscene/node_modules/playwright');
  const outputRoot = process.env.REPORT_CAPTURE_TEST_OUTPUT || fs.mkdtempSync(path.join(os.tmpdir(),'stage-capture-'));
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:600,height:400}});
    let requests = 0;
    page.on('request', () => requests++);
    await page.setContent('<body style="height:800px"><input id="title"><input data-ui-sensitive style="position:absolute;left:20px;top:80px"><button>Save</button><output></output><p id="result"></p><script>document.querySelector("button").onclick=()=>{document.querySelector("output").textContent="Accepted row A";setTimeout(()=>document.querySelector("#result").textContent="Saved row A",100)}</script>');
    await page.locator('[data-ui-sensitive]').fill('synthetic private');
    await page.locator('#title').fill('row A');
    const step = {step_id:'save',action:'Save row A'};
    const delivery = await runExplorationStage({ runId:'sample-'+Date.now(),outputRoot,cases:[
      {id:'A',run: async (record,stop,capture) => {
        assert.equal(await page.locator('#title').inputValue(),'row A');
        const shot = (point,observation,options={}) => capture(page,step,{point,object_ref:'row A',observation,...options});
        await shot('pre_submit','Title contains row A');
        await page.getByRole('button').click();
        assert.equal(await page.locator('output').innerText(),'Accepted row A');
        await shot('receipt','Accepted row A');
        await page.getByText('Saved row A',{exact:true}).waitFor();
        await shot('final','Saved row A');
        await capture(page,{step_id:'query',action:'Inspect row'}, {point:'query',object_ref:'row A',observation:'Saved row A',fullPage:true});
        await capture(page,{step_id:'extra',action:'Review state'}, {point:'author',object_ref:'row A',observation:'Saved row A',reason:'Review the owner field'});
      }}
    ]});
    assert.equal(requests,0);
    const archive = JSON.parse(fs.readFileSync(delivery.observations));
    const [save, query, extra] = archive.cases[0].steps;
    // A relabelled path still belongs to its original capture, even inside the same run.
    const original = fs.readFileSync(delivery.report_html);
    const altered = structuredClone(archive);
    altered.cases[0].steps[1].images[0] = {...save.images[0], step_id:query.step_id};
    fs.writeFileSync(delivery.observations,JSON.stringify(altered));
    const rejected = require('node:child_process').spawnSync('python',['-X','utf8',
      path.resolve(__dirname,'../skills/ui-test-explore/scripts/publish_observations.py'),'--archive',delivery.observations],
      {encoding:'utf8'});
    assert.notEqual(rejected.status,0);
    assert.match(rejected.stderr,/E_EXPLORATION_IMAGE_IDENTITY/);
    assert.deepEqual(fs.readFileSync(delivery.report_html),original);
    assert.deepEqual(save.images.map(i=>i.point),['pre_submit','receipt','final']);
    assert.equal(extra.key_reason,'Review the owner field');
    const html = fs.readFileSync(delivery.report_html,'utf8');
    for (const [image,height] of [[save.images[0],400],[query.images[0],816]]) {
      assert.equal(image.run_id,archive.run_id);
      const bytes = fs.readFileSync(image.path);
      assert.ok(html.includes(bytes.toString('base64')));
      assert.equal(bytes.readUInt32BE(16),600);
      assert.equal(bytes.readUInt32BE(20),height);
      const pixel = await page.evaluate(async base64 => {
        const img = new Image(); img.src = 'data:image/png;base64,' + base64; await img.decode();
        const ctx = document.createElement('canvas').getContext('2d'); ctx.drawImage(img,0,0);
        return [...ctx.getImageData(25,85,1,1).data];
      },bytes.toString('base64'));
      assert.deepEqual(pixel,[0,0,0,255]);
    }
  } finally { await browser.close(); }
});
