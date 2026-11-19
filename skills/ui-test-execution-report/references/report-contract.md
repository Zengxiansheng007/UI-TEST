# Report Contract

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

## HTML Layout Contract

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

```text
<output-root>/
  human-html/<project_group_slug>/<project_slug>/<module_slug>/<YYYY-MM-DD>/<run_id>/report.html
  agent-readable/<project_group_slug>/<project_slug>/<module_slug>/<YYYY-MM-DD>/<run_id>/evidence-index.json
  agent-readable/<project_group_slug>/<project_slug>/<module_slug>/<YYYY-MM-DD>/<run_id>/execution-summary.json
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
