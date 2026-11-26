# CR-20261127-060 · Independent ui-test-evidence delivery

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 32686c7 |

## Summary

Forward the long name and its original request to the selected owner.

## Context And Problem

Issue #60 requires independent evidence and review for existing callers.

## Sections Changed

Skill workflow and local compatibility CLI.

## Decision And Alternatives

Reuse the selected suite loader and the owner's CLI.

## Impact Analysis

Preserves the Packet 3.0 route and original identity. Both aliases return after producing their requested output.

## Validation Evidence

The owned tests compare exact JSON for old and new calls, reject missing sources and stale evidence, and check step lineage. Ticket #60 records the selected suite and runtime receipts.

## Safety And Privacy

Only projected local fields leave the process. Raw response headers are excluded.

## Risks And Follow-up

Whole-suite host navigation is exercised under #71 and #74.
