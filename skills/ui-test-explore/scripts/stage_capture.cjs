/** Capture the live page only at the observation reported by the authorized case. */
const fs = require('node:fs');
const path = require('node:path');
const { createHash, randomUUID } = require('node:crypto');
const points = new Set(['pre_submit','receipt','final','timeout','failure','blocked','unknown','query','author','ordinary']);
const standardMask = 'input[type=password], [data-ui-sensitive], [autocomplete=cc-number], [autocomplete=one-time-code]';

function caseCapture(row, output, caseMasks = []) {
  return async function capture(page, step, moment) {
    const { point, object_ref, observation, reason, fullPage = false, maskSelectors = [] } = moment;
    const { preferred = false, support = 'direct', state_ref, moment_ref, final_goal } = moment;
    const qualifiers = Object.fromEntries(Object.entries({state_ref, moment_ref, final_goal})
      .filter(([, value]) => value !== undefined));
    if (!points.has(point) || typeof fullPage !== 'boolean' ||
        typeof preferred !== 'boolean' || !['context','direct'].includes(support) ||
        (final_goal !== undefined && (point !== 'receipt' || support !== 'direct')) ||
        ![object_ref,observation,step.step_id,step.action,...Object.values(qualifiers),...(point === 'author' ? [reason] : [])]
          .every(value => typeof value === 'string' && value.trim()))
      throw new Error('Invalid capture point, identity or observation');
    let entry = row.steps.find(item => item.step_id === step.step_id);
    if (!entry) {
      entry = structuredClone(step);
      row.steps.push(entry);
    } else if (entry.action !== step.action) {
      throw new Error('Conflicting capture step identity');
    }
    const caption = [object_ref, point, observation].join(' · ');
    const image = {stage:'midscene',run_id:row.run_id,case_id:row.case_id,attempt_ref:row.attempt_ref,
      step_id:step.step_id,point,object_ref,observation,caption,role:point === 'ordinary' ? 'ordinary' : 'key',
      full_page:fullPage,preferred,support,...qualifiers};
    if (reason) { image.reason = reason; entry.key_reason = reason; }
    entry.actual_result = observation;
    (entry.images ||= []).push(image);
    const directory = path.join(output,'images');
    try {
      fs.mkdirSync(directory,{recursive:true});
      if (fs.realpathSync(directory) !== path.join(fs.realpathSync(output),'images'))
        throw Object.assign(new Error('Invalid capture directory'),{code:'E_CAPTURE_ESCAPE'});
      const masks = [standardMask,...caseMasks,...maskSelectors];
      const mask = page.frames().flatMap(frame => masks.map(selector => frame.locator(selector)));
      const bytes = await page.screenshot({fullPage,mask,maskColor:'#000000',type:'png'});
      const captureId = randomUUID();
      const file = path.join(directory,captureId+'.png');
      fs.writeFileSync(file,bytes,{flag:'wx'});
      const receipt = {stage:image.stage,run_id:row.run_id,case_id:row.case_id,attempt_ref:row.attempt_ref,
        step_id:step.step_id,path:file,sha256:createHash('sha256').update(bytes).digest('hex')};
      fs.writeFileSync(path.join(directory,captureId+'.json'),JSON.stringify(receipt),{flag:'wx'});
      Object.assign(image,{path:file,sha256:receipt.sha256,capture_id:captureId,
        width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)});
    } catch (error) {
      if (error.code === 'E_CAPTURE_ESCAPE') throw error;
      image.missing_reason = 'Masked page capture unavailable';
    }
    return image;
  };
}

module.exports = { caseCapture };
