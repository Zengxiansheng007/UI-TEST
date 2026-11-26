# CR-20261127-062 · Asset and experience owners

| Field | Value |
|---|---|
| Status | applied |
| Baseline | d6589b4 |
| Issue | #62 |

## Summary

Query scoped next-run assets and source-bound experiences through the selected suite.

## Context And Problem

The former core held both implementations. Independent queries needed explicit prerequisites and traceable results.

## Sections Changed

Moved asset discovery, revision state, experience lookup and strategy learning to their owners. Added two catalog entries and the direct query commands. Shared core module names and the original learning CLI remain available.

## Decision And Alternatives

The existing selector evaluates project scope, dependencies and permissions. The read-only query computes unregistered discoveries in memory. Existing project writers retain their archival behavior.

## Impact Analysis

Project runtime, catalog and historical imports continue using the same revision store. The experience owner reads the eight-field scope and retains original source references.

## Validation Evidence

Targeted tests cover scoped V2 selection, recorded V1 restrictions, unresolved candidates, source-bound experience, missing inputs, revision concurrency and old clients. The ticket's local runtime receipts cover both selected-suite commands.

## Safety And Privacy

Verification uses local controlled files. No page, model, business submission or credential is needed.

## Risks And Follow-up

The historical script version and archive restore are verified by the run catalog and governance owners during integration.
