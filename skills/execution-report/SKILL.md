---
name: execution-report
description: Use when a UI test engineer wants to rebuild one offline stage report from archived Midscene observations or a sealed Playwright pytest session, preserving original attempts, screenshots and outcomes.
---

# Rebuild a stage report

Open the scripts directory of the selected main UI-Test Skill and run `python ui_test_suite.py --suite <ui-test> execution-report --observations <observations.json> --output <new-directory>` for exploration. For formal results, replace `--observations` with `--session <evidence/sessions/SESSION-…json>`. The session must retain its sealed V5, terminal receipts and evidence tree. Ask for the exact source when several stages match.

## Validation

Read the returned HTML, execution summary and evidence index. Verify the stage ID, case identities and recorded attempts against the supplied original. Return those three artifacts and finish.

## Safety and escalation

For missing, ambiguous or conflicting inputs, return the diagnostic and request the named original or selected installation. The output directory must be new. An offline rebuild consumes recorded evidence and performs no business actions.
