# CR-20261120-032 · 会话报告列出范围外节点

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test-execution-report |
| Change Type | fixed |
| Scope | scripts-and-validation |
| Source | UI-TEST #22 integration review |
| Baseline | fd07e04e2b77b578236390548405df875d4e568c |
| Author | Codex |
| Related Records | CR-20261120-025, CR-20261120-029 |

## Summary

The JSON and HTML expose the controller's unexpected nodes. A contradictory passed disposition is incomplete. Original closure verification is shared with the producer.

## Context And Problem

A passed declaration containing unexpected nodes produced a schema finding but omitted those nodes from the generated report.

## Sections Changed

Session report generator and public CLI regressions.

## Decision And Alternatives

Use the existing V2 session schema and the producer's original transaction verifier. Preserve the source document while rendering each unexpected node.

## Detailed Change

The JSON and HTML expose the controller's unexpected nodes. A contradictory passed disposition is incomplete. Original closure verification is shared with the producer.

## Impact Analysis

Historical V1 acceptance and individual V5 reports keep their existing entry points. Source exit status and the observed process exit remain part of batch review.

## Validation Evidence

Local evidence is in `c22-evidence/final-review`. The source trees for both skills are pinned in `skill-baselines.txt`. The initial reproductions are in `red.xml`; the focused suites and final candidate checks are recorded alongside them.

The first nine checks recorded eight failures and one existing guard. The thirteen focused checks in `candidate.xml` passed. They cover malformed originals, archive closure, refusal after setup, concrete scope notices, independent progress, accepted-conflict protection, cached pass revalidation and the offline report. Both `--require-change-records` validators returned zero findings. A broader first run exceeded the runner's five-minute limit; its partial output remains in `green.xml` and the rerun uses `suite.xml`.

## Safety And Privacy

The regressions use disposable evidence. Scope notices contain the existing decision reference and selected node IDs.

## Risks And Follow-up

This review covers offline evidence readers and synthetic scheduler runs. The original #30 business artifacts retain their original commits and timestamps.
