---
name: plan
description: Prepare a UI automation plan and source-traced main Packet from a source case, PRD, prototype, or explicit web test objective. Use for UI test scope, step assertions, ambiguity checks and evidence requirements before exploration.
---

# UI automation planning

Use the source case, business objective and applicable [planning checklist](references/planning-checklist.md) to identify the five-field scope, branch, priority, test-point owner, component variant, and distinct setup, feature and assertion steps. Trace each step to a dated source or explicit assumption. Record uncertainty, permissions, forbidden actions and evidence needed at each critical change. Keep the Source Case as the case authority. Resolve project output locations through its v2 config and Path Planner for formal assets.

When given a project and identifier, locate its source case within the declared project. Return candidates if multiple versions match. Ask for the exact missing expected result if a decisive business outcome is unspecified. With unresolved P0 scope, environment, permissions or results, return the questions.

Prepare the source JSON using the [worked planning request](assets/playground-wizard.json). Supply the actual case, branch and run identity, risk and source references, constraints and accurate history. Each business assertion has an observable postcondition. Set the Python import path to the selected main Skill's scripts directory for its shared ui_test_core package. Run the selected plan Skill's [planning producer](scripts/build_plan.py) with `--input SOURCE.json --output NEW_PACKET.json` with Python. It prints clarification items or emits one validated Packet 3.0 for exploration. To validate an already prepared Packet or preserve the former producer command, use the selected core's `packet_validator.py --input task.json --output packet.json`. Return the packet, planned steps, evidence expectations and open questions to the requester.

For the public Automation Playground acceptance, copy the [52-section coverage checklist](assets/playground-coverage.csv) to the current plan alongside the Packet. Keep the two phase columns independent. Select representatives across nine classes and recheck section 36 in the current frame. Sections 24 and 42 generate screen simulations. Capture actual HTTP evidence only from naturally triggered UI traffic. The [author's section inventory](https://github.com/ghanendra-sdet/automation-playground/blob/82246d8b4f31d548a5173effb8516f1a2a384e6c/README.md#sections) and [confirmed acceptance](https://github.com/Zengxiansheng007/UI-TEST/issues/57) describe the planned coverage. Replace sample inputs and identities for each new phase. Planning ends on delivery.

## Validation

Check the emitted Packet against the selected main validator. Match its case, branch and run to the source, and verify each decisive postcondition. For the playground, copy the checklist with all phase status cells pending before execution.

## Safety

Planning supplies no permission to operate a page or call a model. Exclude secrets, record write budgets for each proposed stage and stop for clarification when the business outcome or authorization boundary is unresolved.
