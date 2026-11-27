# CR-20261127-075 · Pause an unknown write

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 4003ea8 |
| Target Skill | explore |
| Source | #57 AC-12 review and case-scoped continuation decision |

## Summary

Keep the unknown result and screenshot on the original step, wait for its dependencies and continue independent work in verified separate browser windows.

## Context And Problem

Recording an unknown write returned control to the remaining actions. Capturing and recording that step twice also prevented evidence indexing.

## Sections Changed

Batch fixture, delivery contract and loopback browser regression.

## Decision And Alternatives

Create the independent top-level window in the original browser context and verify the distinct browser window IDs. Hold a legacy callback that cannot consume the fresh page.

## Detailed Change

Exploration preserves identity, pauses the attempt and reports the decision. The main workflow consumes the original unknown observation before script build or formal dispatch.

## Impact Analysis

Uninterrupted callbacks and ordinary declared stops retain their existing behavior. Recovery requires confirmation of the original write.

## Validation Evidence

The record-only path retains a masked unknown-scene capture or a specific missing-image reason. The duplicate identity check preserves the first recorded observation. Legacy and canonical entry regressions exercise historical callback compatibility.

Loopback Chromium test write_pause.test.cjs checks one click, retained screenshot, dependent hold and distinct window IDs for the independent case. A separate negative test with unavailable window verification checks that the callback waits. test_unknown_exploration_handoff.py checks the selected workflow CLI stops before formal execution.

## Safety And Privacy

The fixture operates on local synthetic data. It issues no model request.

## Risks And Follow-up

Callbacks are trusted serial fixture code and must propagate the stop and bind actions to the provided page. This package cannot constrain arbitrary code outside its fixture.

## Integrated review at f02292f

Explicit unknown captures respect scope and waiting cases have zero attempts.

write_pause.test.cjs passed all three serial loopback checks, including zero screenshots for both disallowed explicit capture forms and zero attempts in original events, sealed stage and refreshed SQLite. The create-skill --require-change-records validation reported zero findings.
