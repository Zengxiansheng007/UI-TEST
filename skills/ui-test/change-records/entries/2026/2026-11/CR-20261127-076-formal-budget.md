# CR-20261127-076 · Scoped formal write permits

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | 4003ea8 |
| Source | #57 review, AC-12 |

## Summary

Enforce the approved batch limits before a protected UI write.

## Context And Problem

The workflow verified the budget digest but sent only a batch-wide R2 flag to pytest.

## Sections Changed

Workflow passes the reviewed file and digest. The dispatcher checks effective worker options. The pytest plugin intersects the actual item and project phases with the approved record. The execution data session claims the durable phase permit before returning it.

## Decision And Alternatives

Explicit versioned limits cover nodes, case, branch and phase. A closed historical claim can still deliver its sealed result. Prospective writes need the versioned document.

## Detailed Change

A worker rechecks the digest and run identity at the permit boundary. Exclusive creation reserves one slot across retry and overlapping processes. An unconsumed reservation remains spent.

## Impact Analysis

Read-only formal V5 stays available. Publication, model calls, public runs, and installation are outside this change.

## Validation Evidence

The formal run.py regression selects A and B in one serial batch with one approved slot for A. A obtains its first permit and commits a passing V5, catches the exhausted second-session request before its second effect, and B fails setup before entering the test. The phase-intersection check covers project-only and batch-only permissions, digest drift at consumption, another task's rejected budget, and two independently authorized tasks sharing a batch label. The launch-contract check covers the explicit child options and parallel-group metadata without starting parallel scripts.

The unchanged closed P05 workflow claim resumed in a read-only check with invocation disabled and produced its original PB-dba814a4c8bf9568 report of 15 nodes. Both skill packages passed validate_create_skill.py --require-change-records with zero findings.

A three-node offline regression covers the subsequent worker interruption. A has a sealed passing V5, B was denied before an attempt, and C has an unconfirmed outcome. Both delivery paths now apply the same reserved-run identity rule, preserving the actual run match for attempted nodes. The interruption report retains all three cases in selection order and a repeated invocation starts no new worker.

## Safety And Privacy

Tests use synthetic local files and no secret values. The protected effect is the suite write permit under the reviewed scripts.

## Risks And Follow-up

Arbitrary code that clicks outside the suite permit requires separate host controls.
