# CR-20261127-074 · Independent report reader

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 0778abc |
| Target Skill | ui-test |
| Source | #74 integration regression against #58 |

## Summary

Separate offline report reading from live stage publication imports.

## Context And Problem

The report-only installation failed resolving the absent playwright-run owner while parsing an existing Midscene stage.

## Sections Changed

Execution-report reader imports, main stage publication imports and the relocated reader regression.

## Decision And Alternatives

Import the identifier helper at its defining module. Import the session reader in its formal branch and publication dependencies in the publishing functions.

## Detailed Change

Both historical observation and V5 session inputs remain readable in a selected installation containing only the core and report reader.

## Impact Analysis

Stored sources, report output contracts, publication calls and the pytest finalization owner are unchanged.

## Validation Evidence

The original failing test, existing formal V5 session and exploration originals were exercised in isolated installations. Evidence is in p57-evidence/74/compat.

## Safety And Privacy

Tests replay existing controlled artifacts offline.

## Risks And Follow-up

Recheck the frozen installed candidate before promotion.

The same integration review found four retired names present only in the test machine installation. Four explicit notice-only entries now ship in the repository skills directory. Their fixed responses preserve the observed field conventions. All four remain outside the active catalog. Machine source digests and response comparisons are in archive-provenance.json.
