/** Normal batch boundary for a Midscene fixture. The caller owns the authorized page. */
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const { caseCapture } = require('./stage_capture.cjs');
const { openContinuationWindow } = require('./continuation_window.cjs');

class ExplorationStop extends Error {}
class UnknownWrite extends ExplorationStop {}
const unknownWrites = new Set(['unknown','submitted_unknown','write_unknown','write_unconfirmed','write_outcome_unknown']);

function planDependencies(item, root) {
  const base = path.resolve(root);
  const files = new Set(item.dependencies ?? []);
  const seen = new Set();
  function visit(filename) {
    if (!filename || seen.has(filename)) return;
    seen.add(filename);
    const relative = path.relative(base, filename);
    if (path.isAbsolute(relative) || relative.split(path.sep).some(part => ['..', 'node_modules'].includes(part))) return;
    if (!['.js', '.cjs', '.mjs', '.json', '.ts'].includes(path.extname(filename))) return;
    files.add(relative);
    for (const child of require.cache[filename]?.children ?? []) visit(child.filename);
  }
  if (item.planSource) {
    const file = path.resolve(base, item.planSource);
    files.add(path.relative(base, file)); // Explicit source must pass the bridge's containment check.
    visit(file);
  } else visit(require.main?.filename);
  return [...files];
}

async function runExplorationStage({ runId, outputRoot, cases, page, nativeReplay, python = 'python' }) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(runId) || typeof runId !== 'string')
    throw new Error('Invalid exploration run ID');
  const ids = cases.map(item => JSON.stringify([item.id, item.branch_id ?? item.id, item.attempt ?? '1']));
  if (!cases.length || new Set(ids).size !== ids.length || cases.some(item =>
    typeof (item.attempt ?? '1') !== 'string' || !(item.attempt ?? '1').trim() ||
    (item.branch_id !== undefined && (typeof item.branch_id !== 'string' || !item.branch_id.trim())) ||
    typeof item.id !== 'string' || !item.id.trim() || typeof item.run !== 'function'))
    throw new Error('Expected distinct case attempts and runnable cases');
  const priorCases = new Set();
  for (const item of cases) {
    if (item.dependsOn !== undefined && (!Array.isArray(item.dependsOn) ||
        item.dependsOn.some(id => !priorCases.has(id) || id === item.id)))
      throw new Error('Case dependencies must precede the case');
    if (item.usesStagePage && !page?.context) throw new Error('Missing authorized stage page');
    priorCases.add(item.id);
    const plan = item.plannedSteps ?? [];
    if (!Array.isArray(plan) || plan.some(step => !step || typeof step.step_id !== 'string' ||
      !step.step_id.trim() || typeof step.action !== 'string' || !step.action.trim()) ||
      new Set(plan.map(step => step.step_id)).size !== plan.length) throw new Error('Invalid step plan');
  }
  const bridge = path.join(__dirname, 'publish_observations.py');
  fs.mkdirSync(outputRoot, { recursive: true });
  if (fs.existsSync(path.join(outputRoot, 'midscene', runId)))
    throw Object.assign(new Error('Existing exploration run'), {code: 'EEXIST'});
  const allocation = spawnSync(python, ['-X','utf8',bridge,'--reserve',outputRoot,runId],
    { encoding: 'utf8', windowsHide: true });
  if (allocation.error) throw allocation.error;
  if (allocation.status !== 0) throw new Error(allocation.stderr.trim() || 'Exploration allocation failed');
  const output = JSON.parse(allocation.stdout);
  if (output === null) throw Object.assign(new Error('Existing exploration run'), {code:'EEXIST'});
  const started_at = new Date().toISOString();
  const rows = cases.map(item => ({
    branch_id: item.branch_id ?? item.id, case_id: item.id, node_id: item.id, run_id: runId, attempt_ref: item.attempt || '1',
    status: 'not-executed', planned_steps: structuredClone(item.plannedSteps ?? []), steps: []
  }));
  function checkpoint(event, data) {
    const result = spawnSync(python, ['-X', 'utf8', bridge, '--event', output, runId, event],
      {input: JSON.stringify(data), encoding: 'utf8', windowsHide: true});
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(result.stderr.trim() || 'Stage checkpoint failed');
    if (result.stdout.trim() !== 'null') console.warn('Catalog refresh pending: ' + result.stdout.trim());
  }
  checkpoint('start', {started_at, owners: rows.map(({case_id, branch_id}) => ({case_id, branch_id}))});
  let failure;
  let blocked = false;
  const waiting = new Set(); // A later attempt at the same business case must also wait.
  for (const [index, item] of cases.entries()) {
    const row = rows[index];
    if (waiting.size) {
      const dependencies = (item.dependsOn || []).filter(id => waiting.has(id));
      if (waiting.has(item.id)) dependencies.push(item.id);
      if (dependencies.length) row.reason = 'Waiting for original result of ' + dependencies.join(', ');
      else if (!item.dependsOn || !item.usesStagePage)
        row.reason = 'Independent continuation requires declared dependencies and a fresh stage page';
      if (row.reason) {
        waiting.add(item.id);
        continue;
      }
    }
    let pause;
    let unknownStep;
    let attemptStarted = false;
    const recorded = new Set(); // Only a capture-created step may be completed by its first record.
    function checkWrite(step) {
      if (!unknownWrites.has(step.write_state)) return;
      unknownStep = step;
      step.write_state = 'write_outcome_unknown';
      step.status = 'unknown';
      const position = row.planned_steps.findIndex(planned => planned.step_id === step.step_id);
      if (position >= 0 && row.planned_steps[position+1]) row.stopped_before = row.planned_steps[position+1].step_id;
      pause = new UnknownWrite('Confirm original write result before resuming step ' + step.step_id);
      throw pause;
    }
    function record(step) {
      if (pause) throw pause;
      if (typeof step?.action !== 'string' || !step.action.trim()) throw new Error('Missing action');
      const copy = structuredClone({step_id: String(row.steps.length + 1), ...step});
      const previous = row.steps.find(entry => entry.step_id === copy.step_id);
      if (recorded.has(copy.step_id) || (previous && previous.action !== copy.action))
        throw new Error('Conflicting recorded step identity');
      recorded.add(copy.step_id);
      if (previous) Object.assign(previous, copy, previous.images ? {images:previous.images} : {});
      else row.steps.push(copy);
      checkWrite(previous || copy);
    }
    function stop(reason, beforeStep) {
      if (typeof reason !== 'string' || !reason.trim()) throw new Error('Missing stopping point');
      if (beforeStep !== undefined) {
        if (!row.planned_steps.some(step => step.step_id === beforeStep)) throw new Error('Unknown stop boundary');
        row.stopped_before = beforeStep;
      }
      throw new ExplorationStop(reason);
    }
    try {
      const selected = { planned_steps: row.planned_steps, callback: Function.prototype.toString.call(item.run),
        ...(item.dependsOn !== undefined && {dependsOn:item.dependsOn}), ...(item.usesStagePage && {usesStagePage:true}),
        ...(item.captureUnknown === false && {captureUnknown:false}) };
      const binding = spawnSync(python, ['-X', 'utf8', bridge, '--bind-plan', outputRoot], {
        input: JSON.stringify({node_id: row.node_id, selected_plan: selected, dependencies: planDependencies(item, outputRoot)}),
        encoding: 'utf8', windowsHide: true
      });
      if (binding.error || binding.status !== 0) throw new Error(binding.stderr || 'Exploration plan binding failed');
      row.binding = JSON.parse(binding.stdout);
      row.version = row.binding.version;
      let freshPage;
      if (waiting.size) {
        try {
          const opened = await openContinuationWindow(page);
          freshPage = opened.page;
          row.browser_window = opened.evidence;
        } catch {
          row.reason = 'Waiting for a verified separate browser window in the authorized context';
          waiting.add(item.id);
          continue;
        }
      }
      checkpoint('attempt', {...row, status: 'running'});
      attemptStarted = true;
      const activePage = freshPage || page;
      const captureEvidence = caseCapture(row, output, item.maskSelectors);
      async function scopedCapture(target, step, moment) {
        const excluded = item.captureUnknown === false && (moment.point === 'unknown' || unknownWrites.has(step.write_state));
        const missingReason = excluded ? 'Unknown-scene screenshot excluded by the case capture scope'
          : !target ? 'No authorized active page supplied for the unknown write' : undefined;
        return captureEvidence(target, step, moment, missingReason);
      }
      async function capture(target, step, moment) {
        if (pause) throw pause;
        if (item.usesStagePage && target !== activePage) throw new Error('Capture belongs to another page');
        const image = await scopedCapture(target, step, moment);
        if (unknownWrites.has(step.write_state)) {
          const entry = row.steps.find(saved => saved.step_id === step.step_id);
          entry.write_state = step.write_state;
          checkWrite(entry);
        }
        return image;
      }
      try {
        await item.run(record, stop, capture, activePage);
        if (pause) throw pause;
      } finally {
        if (unknownStep && !unknownStep.images?.some(image => image.point === 'unknown')) {
          await scopedCapture(activePage, unknownStep, {point:'unknown',
            object_ref:unknownStep.object_ref || row.case_id,
            observation:unknownStep.actual_result || 'Original write result unconfirmed'});
        }
        // Leave the original scene available for read-only reconciliation of an unknown result.
        if (freshPage && !pause) await freshPage.close();
      }
      if (!row.steps.length) stop('No observation recorded');
      row.status = 'observed';
    } catch (error) {
      blocked = true;
      row.status = 'blocked';
      row.reason = pause?.message || (error instanceof ExplorationStop ? error.message : 'Executor interrupted; see last recorded observation');
      if (pause) {
        waiting.add(item.id);
        continue;
      }
      if (!(error instanceof ExplorationStop)) failure = { cause: error };
      for (const remaining of rows.slice(index + 1)) remaining.reason = 'Batch stopped at ' + item.id;
    } finally {
      if (attemptStarted) checkpoint('attempt', row);
    }
    if (row.status === 'blocked') break;
  }
  if (nativeReplay && fs.existsSync(nativeReplay) && fs.statSync(nativeReplay).isFile()) {
    rows[0].native_replay_url = pathToFileURL(path.resolve(nativeReplay)).href;
  }
  const batch = { stage: 'midscene', run_id: runId, started_at, ended_at: new Date().toISOString(), cases: rows };
  const child = spawnSync(python, ['-X', 'utf8', bridge, output], {
    input: JSON.stringify(batch), encoding: 'utf8', windowsHide: true
  });
  if (child.error) throw child.error;
  if (child.status !== 0) throw new Error(child.stderr.trim() || 'Exploration publication failed');
  const delivery = { ...JSON.parse(child.stdout), next_action: blocked ? 'review' : 'verify' };
  console.log('Midscene exploration report ' + delivery.report_url);
  if (failure) throw Object.assign(new Error('Exploration executor interrupted', failure), { delivery });
  return delivery;
}

module.exports = { runExplorationStage };
