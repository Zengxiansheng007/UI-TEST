# CR-20261127-065 - Checkpoint schema owner

| Field | Value |
|---|---|
| Status | applied |
| Baseline | dc304f7 |
| Target Skill | ui-test |

## Summary

Expose checkpoint validation, capture and derivation through the selected suite.

## Context And Problem

The original bundle located the handoff implementation relative to its source path.

## Sections Changed

Catalog, command dispatch, schema owner, historical adapter, CLI examples and tests.

## Decision And Alternatives

Keep the existing snapshot and packet formats. Use the same public A2A mapping as the independent handoff command.

## Detailed Change

Validate definitions independently, derive a Packet from persisted facts and name missing execution fields.

## Impact Analysis

Existing entry and import paths call the selected owner. Historical schemas and input fixtures remain readable.

## Validation Evidence

The owner tests cover original commands, missing identity, relocated suites and a complete snapshot round trip.

## Safety And Privacy

Controlled local fixtures; no browser or external call.

## Risks And Follow-up

Installation and suite-wide discovery are covered by #74.
