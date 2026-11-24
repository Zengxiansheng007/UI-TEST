# CR-20261120-025 - Pytest session report

| Field | Value |
|---|---|
| Status | validated |
| Target Skill | ui-test-execution-report |
| Change Type | added |
| Scope | core-skill-md, references-and-assets, scripts-and-validation |
| Source | UI-TEST #22 and #25 |
| Baseline | e1607f163645cdc5ca6245202c3a5766a68dcc5d |
| Related Records | CR-20261118-003 |

## Summary

The report CLI reviews the controller's V2 session independently of the individual V5 case-report envelope.

## Context And Problem

A reviewer could inspect a completed case but could not ask the report CLI which expected nodes or terminals were missing from the batch, or compare the controller's exit with the process outcome observed by its caller.

## Sections Changed

The skill's workflow, report contract and test plan describe the session entry. The CLI selects a source, the batch projection reads it, and public-entry tests exercise the report artifacts.

## Decision And Alternatives

The report reuses the sibling producer's schema, canonical hash and node evidence verifier. The current invocation supplies the session path and the independently observed process exit. Named invocations can bind the expected batch ID.

## Detailed Change

The HTML and JSON expose the source disposition beside the result of verifying its evidence. A missing session, collection uncertainty, worker error, missing or conflicting record or exit mismatch produces an incomplete review. A completed case in a partial batch stays visible.

## Impact Analysis

Case reports still read the V5 envelope. The six-document historical PyCharm V1 acceptance chain stays on its existing entry. Only the new session mode consumes the caller's observed exit code.

## Validation Evidence

The evidence directory is `c22-evidence/t25report`.

| Check | Observed result | Evidence |
|---|---|---|
| CLI through red and green | Missing-session handling went from rejection at argument parsing to a generated incomplete report. Reconciliation initially omitted the lost worker and mismatched batch ID. All 11 focused cases passed after implementation. | `red-missing.txt`, `green-missing.txt`, `red-reconcile.txt`, `green-reconcile.txt` |
| Report suite paired with the #25 producer | 36 passed and six subtests passed, including a real pytest subprocess, removal of one terminal in the temporary copy, historical V1 acceptance and per-case V5 reports. | `full-test.txt` |
| Ordinary and double-worker runs | Both reported passed with two verified parameterized nodes. | `forward/results.jsonl` |
| Worker crash and early exit | Both reported incomplete. The crash preserved the passed neighbor and skipped node. Early exit retained the verified failure and identified the undispatched node. | `forward/results.jsonl` |
| Create-skill change record, sensitive-pattern and package validation | Both validators returned zero findings. | `skill.txt`, `structure.txt` |

### #28 重复投递修订

控制器拒绝重复投递时，报告 JSON 投影 `denied_duplicate_nodes`，HTML 在“重复投递已拒绝”下列出完整节点。先前通过的节点仍展示其可验证终态。控制器记录失败且退出码一致时，整批显示失败；声明通过却携带拒绝记录时显示证据不一致。正式报告入口的 13 项回归通过，额外的矛盾状态检查通过。证据位于专项验收目录 `t28/report-green.xml`、`t28/report-contradiction.xml` 和 `t28/duplicate-report/sessions/467d20838a1b5dd0e9bc/report.html`。

## Safety And Privacy

Batch review reads the supplied local evidence and writes HTML and JSON to the specified report destination. Displayed values are HTML-escaped. The session path is bound to the evidence root and session identity. The existing sensitive-key check runs before projecting a session.

## Risks And Follow-up

The exit code is supplied by the caller. A session review does not issue an external IDE acceptance record. Pair this package with the #25 producer when generating batch reports.
