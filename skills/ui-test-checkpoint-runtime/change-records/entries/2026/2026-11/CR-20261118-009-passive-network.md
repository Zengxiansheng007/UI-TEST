# CR-20261118-009 — Passive network evidence

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test-checkpoint-runtime |
| Issue | #9, AC-008 |

## Summary

Reuse T05 current-page validation. Recovery now omits raw network traces, URL paths and response headers from its recorded network observations. The Node runner receives proxy settings in process memory.

## Context And Problem

An unbound boolean could pass a network assertion, a post-submit endpoint query was retryable, and checkpoint recovery retained arbitrary response headers and raw traces.

## Sections Changed

core-skill-md, scripts-and-validation

## Decision And Alternatives

Reuse the existing T05 listener. Limit the recovery network record to redacted metadata.

## Detailed Change

Reuse T05 current-page validation. Recovery now omits raw network traces, URL paths and response headers from its recorded network observations. The Node runner receives proxy settings in process memory.

## Impact Analysis

New network postconditions require a matched response reference. The confirmed submit budget still governs UI actions.

## Validation Evidence

Two failing unit checks reproduced the original behavior. The visible Edge controlled regression covers successful and failed verification, evidence collection, UI fallback, stale recovery and the Node checkpoint runner. Candidate-bound server and tool records are in .scratch/t08/runtime-4/command-0.json. The read-only case produced GET /case and a browser-initiated GET /status after clicking Check status. The successful and abnormal checks are in .scratch/t08/runtime-4/result.json.

Independent review reproduced two failures in .scratch/t08/review-red.log. Current-config method, path and assertion digests are now checked. UI failures retain the field and outcome without copying expected or observed private values.

## Safety And Privacy

Synthetic authorization, cookie and custom session headers are excluded from network artifacts. Both browser entries used loopback pages.

The main package regression passed 209 tests and the checkpoint package passed 8 tests. The credentials regression generates a fresh synthetic URL parameter for each run.

## Risks And Follow-up

Coverage is limited to the controlled execution paths and synthetic data verified for #9.
