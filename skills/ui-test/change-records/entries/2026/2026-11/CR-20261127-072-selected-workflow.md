# CR-20261127-072 · Approved multi-stage workflow

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 7deae7b |
| Target Skill | ui-test |
| Source | UI-TEST #72 |

## Summary

Use the main entry for authorized plan, exploration, verification, optional script building and formal execution.

## Context And Problem

Independent capability delivery needed a common caller to retain earlier reports and identify the next stage prerequisites.

## Sections Changed

SKILL.md, CLI, workflow requirements and executable regression test.

## Decision And Alternatives

Call the selected owners, pass the approved exploration run identity into formal execution, and resolve stage outputs from the project layout.

## Detailed Change

Bind the request digest and selected scripts before executing a stage. Return the prior report with a reason when a prerequisite is absent. Resume the same exploration without creating another attempt.

## Impact Analysis

Existing individual child entries continue to return their own deliverables. The original formal runner retains its approvals, serial default and V5 assertions.

## Validation Evidence

See ticket evidence under p57-evidence/72 and the through-entry test test_selected_workflow.py.

## Safety And Privacy

Local controlled inputs are used for offline qualification. Live runs need their own accurate action approval.

## Risks And Follow-up

The independent real Automation Playground run and complete installation acceptance belong to #73 and #74.
