# CR-20261127-060 · Step evidence and review routing

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 5ec3a37 |
| Issue | #60 |

## Summary

Register the evidence and review owners with both legacy aliases.

## Context And Problem

Selected-suite resolution needs a catalog entry for each implementation.

## Sections Changed

Two capabilities in references/capabilities.json describe their inputs, prerequisites, outputs, aliases and Packet route.

## Decision And Alternatives

Keep collect-evidence on the evidence entry and the review state on review.

## Impact Analysis

Both generations of names resolve to the same package. A request to collect evidence may originate in the verify state.

## Validation Evidence

Selected-suite resolves and Packet checks are recorded under #60. The entry tests cover original and indexed inputs, missing material and stale evidence.

## Safety And Privacy

Routing reads metadata. Qualification uses controlled local observations.

## Risks And Follow-up

Fresh-chat natural-language selection is covered by #71 and #74.
