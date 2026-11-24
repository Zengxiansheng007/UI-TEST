/** Normal batch boundary for a Midscene fixture. The caller owns the authorized page. */
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const { caseCapture } = require('./stage_capture.cjs');

class ExplorationStop extends Error {}

async function runExplorationStage({ runId, outputRoot, cases, nativeReplay, python = 'python' }) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(runId) || typeof runId !== 'string')
    throw new Error('Invalid exploration run ID');
  const ids = cases.map(item => JSON.stringify([item.id, item.attempt ?? '1']));
  if (!cases.length || new Set(ids).size !== ids.length || cases.some(item =>
    typeof (item.attempt ?? '1') !== 'string' || !(item.attempt ?? '1').trim() ||
    typeof item.id !== 'string' || !item.id.trim() || typeof item.run !== 'function'))
    throw new Error('Expected distinct case attempts and runnable cases');
  for (const item of cases) {
    const plan = item.plannedSteps ?? [];
    if (!Array.isArray(plan) || plan.some(step => !step || typeof step.step_id !== 'string' ||
      !step.step_id.trim() || typeof step.action !== 'string' || !step.action.trim()) ||
      new Set(plan.map(step => step.step_id)).size !== plan.length) throw new Error('Invalid step plan');
  }
  const parent = path.resolve(outputRoot, 'midscene');
  fs.mkdirSync(parent, { recursive: true });
  const output = path.join(parent, runId);
  fs.mkdirSync(output); // Reserve once before any UI action to prevent accidental re-execution.
  const rows = cases.map(item => ({
    case_id: item.id, node_id: item.id, run_id: runId, attempt_ref: item.attempt || '1',
    status: 'not-executed', planned_steps: structuredClone(item.plannedSteps ?? []), steps: []
  }));
  let failure;
  let blocked = false;
  for (const [index, item] of cases.entries()) {
    const row = rows[index];
    function record(step) {
      if (typeof step?.action !== 'string' || !step.action.trim()) throw new Error('Missing action');
      row.steps.push(structuredClone(step)); // Freeze the actual observation before the next action.
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
      await item.run(record, stop, caseCapture(row, output, item.maskSelectors));
      if (!row.steps.length) stop('No observation recorded');
      row.status = 'observed';
    } catch (error) {
      blocked = true;
      row.status = 'blocked';
      row.reason = error instanceof ExplorationStop ? error.message : 'Executor interrupted; see last recorded observation';
      if (!(error instanceof ExplorationStop)) failure = { cause: error };
      for (const remaining of rows.slice(index + 1)) remaining.reason = 'Batch stopped at ' + item.id;
      break;
    }
  }
  if (nativeReplay && fs.existsSync(nativeReplay) && fs.statSync(nativeReplay).isFile()) {
    rows[0].native_replay_url = pathToFileURL(path.resolve(nativeReplay)).href;
  }
  const batch = { stage: 'midscene', run_id: runId, cases: rows };
  const bridge = path.join(__dirname, 'publish_observations.py');
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
