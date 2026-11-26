# CR-20261127-063 - Separate verification and script building

| Field | Value |
|---|---|
| Status | applied |
| Baseline | d6324ad |
| Target Skill | ui-test-verify |

## Summary

Split standalone verification and script compilation under the selected suite.

## Context And Problem

Issue #63 requires reviewable assertions and independently versioned scripts while retaining public calls.

## Sections Changed

core-skill-md, references-and-assets, downstream-and-handoff

## Decision And Alternatives

Transfer the existing compiler and comparator to their owners and forward historical imports.

## Detailed Change

Verify records the primary observation and a single equivalent fallback. Script generation uses the existing immutable release coordinator.

## Impact Analysis

Legacy verification requests, compiler CLI and imports resolve to the same selected implementations.

## Validation Evidence

See owner action review tests, compiler V1/V2, sync and staged-write regression tests.

## Safety And Privacy

Offline synthetic inputs. Compilation starts no attempt and performs no business submission.

## Risks And Follow-up

Live public-page execution is handled separately by #73.
