# CR-20261127-064 · Selected-suite UI-test handoff

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 4753370 |
| Target Skill | ui-test |

## Summary

Move the local handoff owner and the Packet validation call to the selected suite.

## Context And Problem

The historical mapper located a validator by its neighboring directory. Separate installations could resolve different code.

## Sections Changed

references-and-assets, scripts-and-validation.

## Decision And Alternatives

The new entry calls the selected suite package. Existing commands and the pack API delegate through the same loader.

## Detailed Change

Preserve the source identity, scope, history and references in both derived packets and keep deterministic packet IDs. Reject invalid sources and sensitive references before publishing an output.

## Impact Analysis

Checkpoint callers continue using the original Python entry. The catalog supplies both command names.

## Validation Evidence

See the owner tests for relocated commands, selected schema, historical CLI, project output, provenance and refusal cases. Ticket evidence is retained in p57-evidence/64.

## Safety And Privacy

Controlled local fixture packets only. CLI rejection omits invalid input values.

## Risks And Follow-up

Host-level discovery and complete-suite navigation are checked under #74.
