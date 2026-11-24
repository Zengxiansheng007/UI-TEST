# Report Contract

## Pytest session review

Use the session file selected for the invocation, under the producer's evidence root. In PowerShell, capture `$LASTEXITCODE` immediately after the pytest process returns. A launcher can supply its child's `returncode` directly.

```powershell
python scripts/generate_report.py --session-result $sessionFile --evidence-root $evidenceRoot --observed-exit-code $pytestExit --expected-batch-id $batchId --output-root $reportRoot
```

Omit `--expected-batch-id` for an unnamed invocation. If the caller lost the process outcome, omit `--observed-exit-code` and report the incomplete observation. Session mode reads the strict V2 document and validates its schema, digest, filename identity, worker and collection records, expected node coverage, unique node and run IDs, and the producer's terminal/receipt evidence. Each row retains the producer's disposition and shows whether its evidence verified. Missing expected nodes are listed separately. A named batch is checked against the caller's expected ID.

A verified session produces the shared Playwright stage HTML under `<output-root>/stage-reports/<source-path-hash>/`, with the session diagnostics inside the same document. Incomplete sessions return `artifact_kind=session-diagnostic`. With `--diagnostic`, the HTML and JSON share the historical session review under `<output-root>/sessions/<source-path-hash>/`. The command prints their paths and the batch status. Its exit code indicates whether report generation succeeded. Use the JSON `status` for the batch outcome. A passed batch needs a clean collection, verified passing evidence for every expected node, a matching successful controller result and the caller's observed zero exit. Incomplete reviews retain readable node records. The supplied exit code is the caller's observation. Independent PyCharm acceptance requires the existing external acceptance records. Use the case-report input for historical V1-backed acceptance records.

In single-run mode `--input` projects verified V5 steps through the shared stage renderer. Use `--diagnostic` when the historical attachment/API table layout is explicitly required.

## Required Input Shape

The generator accepts a UTF-8 JSON object:

```json
{
  "report": {},
  "run_result": {},
  "grouping": {},
  "safety": {},
  "steps": [],
  "attachments": [],
  "api_assertions": [],
  "failures": [],
  "midscene": {},
  "playwright": {},
  "score": {},
  "promotion": {}
}
```

## Required Fields

| Object | Field | Required |
|---|---|---|
| `report` | `report_id`, `run_id`, `case_id`, `case_name`, `status`, `started_at`, `ended_at`, `execution_date` | Yes |
| `run_result` | canonical `ui-test.run-result.v5`, including `run_result_hash` | Yes |
| `grouping` | `project_group`, `project`, `module`, `project_group_slug`, `project_slug`, `module_slug` | Yes |
| `steps[]` | `step_id`, `action`, `expected_result`, `actual_result`, `status` | Yes |
| `steps[].ui_evidence` | `attachment_id`, `path`, `captured_at`, `visible_state_summary`, `redaction_applied` | Required for UI-changing steps unless `missing_reason` exists |
| `steps[].api_assertion` | `api_assertion_id`, `method`, `url_template`, `http_status`, `assertion_status` | Required for API steps unless `missing_reason` exists |

## Historical diagnostic HTML layout (`--diagnostic`)

`report.html` must render the step table as the human evidence source of truth:

| Column | Behavior |
|---|---|
| `UI 图片` | Shows a real thumbnail in the cell. Clicking opens a viewport-level viewer outside the table, with the original image bytes, path and evidence JSON. |
| `接口断言` | Shows API/assertion ID in the table cell. Expands to redacted JSON details, request/response summary, JSONPath assertions, and raw JSON path. |

Chapter 5 is an attachment index only. Chapter 6 is an API summary index only.

### Full-Size Screenshot Viewer

- Desktop viewer: approximately 96% viewport width and 94% viewport height; mobile: full available viewport. Table columns must not constrain its size.
- Open in fit-width mode, retaining vertical scrolling for long screenshots. Provide fit-window, 1:1 original pixels, zoom in/out (10%-400%), mouse drag and native touch scrolling.
- Escape and the visible close control close the viewer, restore background scrolling and return keyboard focus to the originating thumbnail.
- The original capture bytes and optional SHA-256 remain unchanged. Use local PNG/JPEG/GIF/WebP images or validated image data URIs; missing/unsupported images show an explicit missing reason rather than a fabricated illustration.
- The shared renderer is `scripts/image_viewer.py`: `render_image_evidence(evidence, title)` for a cell and `install_image_viewer(html)` once per document. Scripts and CSS are embedded for offline opening.
- Test a landscape image, a long screenshot, actual-size inspection, zoom, pan/scroll, close/reopen, Escape and keyboard focus on desktop and mobile.
- This display component does not grant RunResult compatibility, execution permission, release status or report approval. Exploration reading projections retain their original result type and status.

Status governance:

- The generator consumes canonical RunResult V5 and never recalculates pass/fail from report steps.
- `report.status`, execution summary, evidence index and copied `run-result.json` must preserve the canonical result identity and hash.
- Legacy report input without RunResult V5 is migration-only and must fail closed.

## Output Layout

For single-run `--input`, the stage layout root is `<output-root>/stage-reports/`. Explicit `--diagnostic` retains the historical layout root `<output-root>/`. Both modes use the tree below relative to their own layout root. Deliver the CLI's `report_url`; `report_html`, `evidence_index`, `execution_summary` and `run_result` identify its associated files. Repeating the same mode for the same run returns the same paths.

```text
<layout-root>/
  human-html/<project_group_slug>/<project_slug>/<module_slug>/<YYYY-MM-DD>/<run_id>/report.html
  agent-readable/<project_group_slug>/<project_slug>/<module_slug>/<YYYY-MM-DD>/<run_id>/evidence-index.json
  agent-readable/<project_group_slug>/<project_slug>/<module_slug>/<YYYY-MM-DD>/<run_id>/execution-summary.json
  agent-readable/<project_group_slug>/<project_slug>/<module_slug>/<YYYY-MM-DD>/<run_id>/run-result.json
```

Directory governance:

- Path segments must be filesystem-safe.
- Long `run_id` values may be shortened in the directory name with a stable hash suffix.
- The original `run_id` must remain unchanged inside `report.html`, `evidence-index.json`, and `execution-summary.json`.
- Generators should keep each path segment under 80 characters to avoid Windows path-length failures in nested report centers.

## Redaction Rules

The generator must fail on obvious sensitive key names or values:

- `password`
- `passwd`
- `authorization`
- `cookie`
- `set-cookie`
- `token`
- `secret`
- `api_key`
- `x-token`

Allowed examples may include these terms only in policy text or redaction summaries, not as live values.

Set run_root relative to the input JSON and retain the sealed resolved-test-data file at its original relative reference. Supply report.transaction_id, session_id and node_id from the execution identity. Pair this package with its sibling ui-test producer package and locked Python dependencies. The report reads the transaction from run_root/finalization and verifies its commit, receipt and objects. Missing records yield not_provided. To present external acceptance, supply external_acceptance_refs with six run-root-relative JSON paths keyed by pytest_session_result, acceptance_result, approval_record, execution_context, terminal and process_evidence. The producer validates the complete chain. The report records the evaluation authority, result reference and acceptance hash.

## 正式执行结束后的交付

正常 pytest 正式会话收尾时读取该会话的节点、尝试及已提交 V5，并输出一个可打开的阶段报告链接。
Codex 调度由最外层批次负责发布，同一批次的所有子会话汇总到一份 HTML。
将输出的 `UI-Test stage report` 链接直接交给工程师。报告目录同时包含 execution-summary.json 和 evidence-index.json。
这条链路需要 ui-test 与 ui-test-execution-report 两个并列技能包。报告生成失败时记录错误，按已归档结果重试交付。
