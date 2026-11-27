# CR-20261127-071 · Selected suite routing

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 3d131df |
| Target Skill | ui-test |
| Source | UI-TEST #71, parent #57 |

## Summary

Resolve validated Packets from one selected capability catalog with explicit ambiguity.

## Context And Problem

New capabilities must be discoverable by both consumers with one catalog entry.

## Sections Changed

core-skill-md, scripts-and-validation, references-and-assets.

## Decision And Alternatives

Keep the execution policy in the main workflow and the explicit consultation policy in the advisor. Reuse the selected installation's JSON catalog.

## Detailed Change

Resolve validated Packets from one selected capability catalog with explicit ambiguity. The workflow entry participates in consultation only. The existing authoring map remains available when a UI suite is missing.

## Impact Analysis

Old Packet callers retain compatible child names. Public navigation selects the canonical Skill. Additional capability entries require no consumer dispatch change.

## Validation Evidence

Ticket evidence under p57-evidence/71 includes CLI success and refusal receipts, historical routing tests and the isolated revision-stamp delivery.

## Safety And Privacy

Only controlled offline inputs are used. The consultation reads the catalog as data.

## Risks And Follow-up

Integrated catalog completeness and host-level discovery are checked under #74.
