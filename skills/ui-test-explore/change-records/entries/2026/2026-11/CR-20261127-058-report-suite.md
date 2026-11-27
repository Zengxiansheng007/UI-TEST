# CR-20261127-058 - Selected stage report owner

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 32686c7 |
| Target Skill | ui-test-explore |

## Summary

Validate observations with the selected report owner before reserving originals.

## Context And Problem

Report imports previously depended on neighboring installation folders.

## Sections Changed

scripts-and-validation.

## Decision And Alternatives

Resolve the selected main installation once and use its owner registry. Keep existing command semantics.

## Detailed Change

Validate observations with the selected report owner before reserving originals.

## Impact Analysis

The exploration producer and the pytest session finalizer both consume the same rendering package.

## Validation Evidence

See the selected-suite CLI tests and existing report tests for renderer parity, session verification and compatibility.

## Safety And Privacy

Offline reconstruction reads original evidence and writes its own directory.

## Risks And Follow-up

Full host discovery and routing are covered by #71 and #74.
