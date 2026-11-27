# CR-20261127-077 · Recover a missing exploration step index

| Field | Value |
|---|---|
| Status | validated |
| Target Skill | explore |
| Baseline | 4003ea8 |
| Source | #57 integration review, interrupted publication |

## Summary

Archive redelivery derives the step index from the original saved observations when it is missing.

## Context And Problem

The first publication can stop between creating observations.json and publishing step-evidence.json. The archive command then previously returned a report with no index.

## Sections Changed

The publication helper, archive instructions and public CLI regression cover this interruption.

## Decision And Alternatives

Reuse the evidence owner's index builder and atomic publication. A subsequent delivery reuses the index and the original attempts.

## Impact Analysis

Both exploration entry names reach the same archive implementation. The workflow can consume the recovered step index.

## Validation Evidence

The controlled archive test first failed because the response lacked step_evidence. The repaired CLI returned a pointer to the saved step and its source digest. Running it again preserved observation bytes and the index modification time.

## Safety And Privacy

The regression uses synthetic local observations. Recovery starts no browser or model call.

## Risks And Follow-up

Invalid or unavailable original evidence still requires investigation at its source.
