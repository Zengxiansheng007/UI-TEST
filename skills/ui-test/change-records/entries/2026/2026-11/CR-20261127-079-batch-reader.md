# CR-20261127-079 · Offline batch report

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 4003ea8 |
| Target Skill | ui-test |
| Source | #57 AC-05 review |

## Summary

Rebuild a published dispatch batch under its original stage ID.

## Context And Problem

A dispatched stage can span several sealed pytest sessions. Selecting one session omits cases and reports a different stage identity.

## Sections Changed

Public CLI, source selection instructions, journal reconciliation, report links, and CLI tests.

## Decision And Alternatives

Share the publisher's row reconciliation and stage identity derivation. The journal gives original ordering, exact session hashes and run IDs. Stage metadata independently identifies the published attempts.

## Detailed Change

Read the terminal batch, validate its sealed sessions and V5, reconcile published identity, then render into a new directory. The footer resolves source files relative to the original project.

## Impact Analysis

Only publication reserves runs and updates the catalog. The report-only installation still reads observation and standalone session inputs.

## Validation Evidence

The baseline CLI rejected the new selector. Public reconstruction of historical PB-dba814a4c8bf9568 produced 15 cases, byte-identical summary and evidence index, 17 matching image hashes and 94 matching resolved files. All 1027 source files retained their original hashes. Controlled tests cover a failed two-session batch, session tampering, shared nodes across distinct attempts and single-session compatibility.

## Safety And Privacy

The verification reads retained public-test evidence, adds zero attempts, and includes no credentials in the change.

## Risks And Follow-up

The batch reader requires the original journal path and archived stage metadata. Live page execution was outside the offline change.
