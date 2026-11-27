# CR-20261127-070 · Formal execution owner

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 4753370 |
| Target Skill | ui-test |

## Summary

Issue #70 gives formal execution to playwright-run.

## Context And Problem

Existing pytest projects depend on the plugin import and dispatcher command.

## Sections Changed

references-and-assets, scripts-and-validation.

## Decision And Alternatives

Resolve one plugin from the selected suite. Keep historical commands as forwarding entries.

## Detailed Change

The owner dispatches selected nodes and validates formal V5 eligibility. An interrupted batch report identifies unconfirmed work and unstarted nodes while retaining verified neighbor receipts.

## Impact Analysis

Existing pytest, IDE and Codex launch paths share the owner. Core transaction, evidence and catalog schemas retain their existing formats.

## Validation Evidence

Local selected-node and interrupted dispatch tests exercise the public CLI and original pytest paths. Formal read-only candidates cover successful, failed and rejected evidence.

## Safety And Privacy

Tests use an isolated project and synthetic observations. Dispatch retains the task-scoped parallel instruction, credential boundary and phase write budget.

## Risks And Follow-up

The integration and public website checks belong to #72 and #73.
