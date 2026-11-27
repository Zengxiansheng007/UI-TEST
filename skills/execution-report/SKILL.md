---
name: execution-report
description: Use when rebuilding an offline stage report from Midscene observations, a published Playwright dispatch batch, or a sealed standalone pytest session with its original attempts and screenshots.
---

# Rebuild a stage report

Open the scripts directory of the selected main UI-Test Skill and run `python ui_test_suite.py --suite <ui-test> execution-report --observations <observations.json> --output <new-directory>` for exploration.

For a dispatched Playwright stage, use `execution-report --task-ref <original-dispatch-journal> --batch-ref <batch-id> --output <new-directory>`. Keep the journal at its original path and retain the published stage record, all referenced sessions, terminal receipts, V5 and evidence. Select an output outside the original project. This command reassembles every journal row in order under the published PB stage ID.

For a standalone pytest session, use `execution-report --session <evidence/sessions/SESSION-…json> --output <new-directory>`. This selects exactly that session. Ask for the source and batch ID if several stages match.

The [report reader](scripts/__init__.py) loads the producer for the selected input. Both stages use the [shared stage renderer](scripts/stage_report.py).

## Validation

Read the returned HTML, execution summary and evidence index. Verify the stage ID, case identities and recorded attempts against the supplied original. Return those three artifacts and finish.

## Safety and escalation

For missing, ambiguous or conflicting inputs, return the diagnostic and request the named original or selected installation. The output directory must be new. An offline rebuild consumes recorded evidence and performs no business actions.
