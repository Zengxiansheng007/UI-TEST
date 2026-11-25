/** Normal batch boundary for a Midscene fixture. The caller owns the authorized page. */
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const { caseCapture } = require('./stage_capture.cjs');

class ExplorationStop extends Error {}

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

async function runExplorationStage({ runId, outputRoot, cases, nativeReplay, python = 'python' }) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(runId) || typeof runId !== 'string')
    throw new Error('Invalid exploration run ID');
  const ids = cases.map(item => JSON.stringify([item.id, item.branch_id ?? item.id, item.attempt ?? '1']));
  if (!cases.length || new Set(ids).size !== ids.length || cases.some(item =>
    typeof (item.attempt ?? '1') !== 'string' || !(item.attempt ?? '1').trim() ||
    (item.branch_id !== undefined && (typeof item.branch_id !== 'string' || !item.branch_id.trim())) ||
    typeof item.id !== 'string' || !item.id.trim() || typeof item.run !== 'function'))
    throw new Error('Expected distinct case attempts and runnable cases');
  for (const item of cases) {
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
      const selected = { planned_steps: row.planned_steps, callback: Function.prototype.toString.call(item.run) };
      const binding = spawnSync(python, ['-X', 'utf8', bridge, '--bind-plan', outputRoot], {
        input: JSON.stringify({node_id: row.node_id, selected_plan: selected, dependencies: planDependencies(item, outputRoot)}),
        encoding: 'utf8', windowsHide: true
      });
      if (binding.error || binding.status !== 0) throw new Error(binding.stderr || 'Exploration plan binding failed');
      row.binding = JSON.parse(binding.stdout);
      row.version = row.binding.version;
      checkpoint('attempt', {...row, status: 'running'});
      await item.run(record, stop, caseCapture(row, output, item.maskSelectors));
      if (!row.steps.length) stop('No observation recorded');
      row.status = 'observed';
    } catch (error) {
      blocked = true;
      row.status = 'blocked';
      row.reason = error instanceof ExplorationStop ? error.message : 'Executor interrupted; see last recorded observation';
      if (!(error instanceof ExplorationStop)) failure = { cause: error };
      for (const remaining of rows.slice(index + 1)) remaining.reason = 'Batch stopped at ' + item.id;
    } finally {
      checkpoint('attempt', row);
    }
    if (blocked) break;
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
