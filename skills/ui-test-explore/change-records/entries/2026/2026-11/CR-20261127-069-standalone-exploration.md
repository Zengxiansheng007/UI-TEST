# CR-20261127-069 - Standalone exploration

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 4753370 |
| Target Skill | ui-test-explore |

## Summary

Existing fixtures and archived-observation commands resolve the selected explorer. The canonical Skill owns instructions, observations and return semantics.

## Context And Problem

#69 requires standalone exploration through short and historical names.

## Sections Changed

core-skill-md, references-and-assets, scripts-and-validation, downstream-and-handoff

## Decision And Alternatives

Keep the existing authorized batch callback contract and select the existing evidence, registration and report implementations.

## Detailed Change

Existing fixtures and archived-observation commands resolve the selected explorer. The canonical Skill owns instructions, observations and return semantics.

## Impact Analysis

Direct exploration returns the current observations, step evidence, stage and one report. The main Skill owns formal execution.

## Validation Evidence

Run skills/explore/tests/standalone.test.cjs. The test reads the two-case report, archived attempt identities and evidence pointers.

## Safety And Privacy

Controlled test inputs contain no credentials or page traffic.

## Risks And Follow-up

Live public-page acceptance is tracked by #73.
