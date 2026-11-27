# CR-20261127-069 - Standalone exploration

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 4753370 |
| Target Skill | evidence |

## Summary

Exploration batch publication can index the observations preceding a stop, including a stage with unstarted or blocked empty attempts. Direct requests for missing step material retain the existing error.

## Context And Problem

#69 requires standalone exploration through short and historical names.

## Sections Changed

scripts-and-validation

## Decision And Alternatives

Keep the existing authorized batch callback contract and select the existing evidence, registration and report implementations.

## Detailed Change

Exploration batch publication can index the observations preceding a stop, including a stage with unstarted or blocked empty attempts. Direct requests for missing step material retain the existing error.

## Impact Analysis

Direct exploration returns the current observations, step evidence, stage and one report. The main Skill owns formal execution.

## Validation Evidence

Run skills/explore/tests/standalone.test.cjs. The test reads the two-case report, archived attempt identities and evidence pointers.

## Safety And Privacy

Controlled test inputs contain no credentials or page traffic.

## Risks And Follow-up

Live public-page acceptance is tracked by #73.
