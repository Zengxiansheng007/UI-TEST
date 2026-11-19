# CR-20261118-005 — checkpoint execution snapshot

Issue #5 covers AC-003 and the checkpoint part of AC-009. The legacy bundle derived task identity from checkpoint metadata. The capture CLI now binds current task and run facts to reusable steps, checks the main Packet and derives a stable Packet with snapshot provenance. The bundle uses the shared A2A packer. Legacy examples remain available to the historical validator.

Validation: initial capture test failed on missing entry. All 10 checkpoint tests then passed, including capture and bundle subprocesses, two-run separation, stable regeneration and old input rejection.

| Field | Value |
| --- | --- |
| Status | validated |

## Summary

Capture and bundle carry current task identity.

## Context And Problem

Legacy bundles inferred run metadata.

## Sections Changed

CLI, fixture examples, usage and regressions.

## Decision And Alternatives

Require complete current inputs at capture time.

## Impact Analysis

Old bundles can no longer launch new tasks.

## Validation Evidence

Ten checkpoint tests passed, including public subprocess invocations.

## Safety And Privacy

Fixtures contain local synthetic references only.

## Risks And Follow-up

Host installation and integrated UI acceptance remain separate.

Independent review identified missing applicability and per-step evidence. Public capture now takes task metadata without steps, checks definition scope, maps definition action, risk and verification into Packet steps, and attaches observed step status and references. The main Packet schema accepts these optional step fields.
