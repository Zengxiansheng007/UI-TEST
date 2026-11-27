# Midscene batch delivery

Wrap the approved batch inside its normal Midscene Playwright fixture. Supply the existing Python runtime, the governed output root, a fresh run ID and the complete ordered checklist. One callback corresponds to one case. Choose the page and context per the approved packet. Specialized explorations supply their own case callbacks to the same entry.

For a batch containing writes, provide `page` from the fixture's authorized Playwright BrowserContext. Give every case `dependsOn` (earlier case IDs, or an empty array for independent cases) and `usesStagePage: true`. Implement `run(record, stop, capture, page)`; bind locators and Midscene operations to that invocation's page. Never capture a prior page or agent in this callback. Existing closed-over read-only callbacks remain supported for uninterrupted batches.

When a submitted write has no deterministic result, call the awaited capture with the original step ID, action, `write_state: 'write_outcome_unknown'` and the unknown observation. Alternatively capture the scene first and call `record` with that step ID, action and write state. Let the resulting stop propagate. Serial fixture actions must finish before reporting their outcome. The original attempt remains blocked for confirmation. Dependent cases and repeated attempts wait. The runner opens a new page for each declared independent case in the same authorized context. It withholds callbacks that cannot establish independence and accept a fresh page. Review the original identity, screenshot and read-only result evidence before any separately authorized resumption. Never repeat the submission to determine its outcome.

If `record` first reports the unknown write, the fixture captures the masked active page at the stop boundary unless that step already has an unknown-scene capture. Provide a page only within its authorized capture scope. Set `captureUnknown: false` on a case whose scope excludes that screenshot. The report retains the specific reason for a missing image when the page or capture permission is unavailable.

```js
const { runExplorationStage } = require(pathToExploreSkill + '/scripts/exploration_stage.cjs');
const delivery = await runExplorationStage({
  runId, outputRoot, python, nativeReplay, // Optional existing local replay file
  cases: [{
    id: 'read-row', attempt: '1',
    planSource: __filename, // Project-local module defining this callback. Its loaded project imports are retained.
    dependencies: [], // Additional project-relative JavaScript or JSON plan dependencies loaded dynamically.
    run: async (record, stop, capture) => {
      const visible = await aiQuery('string, visible title of the target row');
      await capture(page, {step_id: 'inspect', action: 'Inspect target row'}, {
        point: 'query', object_ref: 'Reviewed target row', observation: visible
      });
      if (visible !== expectedTitle) stop('Target row title differed');
    }
  }]
});
```

The query above illustrates a read-only case. Only use approved operations and sanitized observations for the actual packet. Call `record(step)` immediately after the observed action or state. Each step carries `action`, its actual observation in `actual_result`, and optionally `step_id`, `expected_result`, `status`, `reason`, `key_reason`, and an ordered `images` list. Use the capture callback for stage images. It records the owning run, case, attempt and step, the masked original's SHA-256, and an independent capture receipt in the run’s images directory. Provide an existing replay file if the native runtime has finalized one. Preserve diagnostic replays produced later in the native runtime's own output.

Return report_url, observations, step_evidence and stage_record. next_action is a compatibility hint only. Stop after this delivery. A declared stop returns a review handoff with the remaining cases recorded as unexecuted. An unexpected executor exception publishes collected observations first and propagates the error with `error.delivery`. A missing report is a delivery failure. Keep each run's observations and returned paths under its own directory. Opening the report or reviewing existing observations requires no model or browser execution.

Use distinct `attempt` strings for separately authorized attempts at one case. For a known checklist, pass `plannedSteps` with `step_id`, `action` and optional `expected_result`. A callback that stops before a known step can call `stop(reason, stepId)`. Its remaining planned steps are unexecuted. Missing observations without a confirmed stop boundary have unknown outcomes. Archive redelivery verifies the capture receipt and image digest before publishing. Preserve the run directory with its images and receipts. An explicitly missing capture retains its local reason.

To redeliver an archived exploration, run `python scripts/publish_observations.py --archive <run-directory>/observations.json` from this skill. When publication stopped after saving the observations, this command derives the missing step index from the saved attempts before returning the report. It preserves the original observations and reuses an existing index. Return the URL and step index from the delivery.

Call the third callback argument at the actual observation on the authorized Playwright page. Use `pre_submit` after checking the filled fields, `receipt` after observing a meaningful acknowledgement and `final` after verifying the target result. Capture `timeout` when a wait ends without the expected result. Use `failure`, `blocked`, or `unknown` for the actual observed exception scene, leaving earlier routine views ordinary. A synchronous UI may expose only the final state. For `author`, supply a nonempty `reason`. Repeat calls with the same step ID and action to keep multiple pictures on that step. Use `ordinary` for routine navigation. Configure the case's `maskSelectors` for sensitive text, fields and images in the approved page; password, marked sensitive, payment number and one-time-code fields get standard masks. Only pass reviewed, nonsensitive object labels and observations. Set `fullPage: true` for explicit cross-screen review. A missing masked capture carries a reason.

同一尝试中的截图以对象、观察时点和业务状态归组。同一动作留下多图时，显式传入相同的 `object_ref`、`point`、`state_ref`（默认用 `observation`）；区分同类事件的多次发生时传 `moment_ref`。作者实际核对画面后可用 `preferred` 指定本组代表图。能读出对象与状态的图标 `support="direct"`（默认）；只提供上下文的图标 `support="context"`，保留在索引。只有回执本身满足用例目标且画面足以证明时，才给该图填写 `final_goal`，记录具体目标。后续状态变化另行记录。
