---
name: a2a-handoff
description: Convert ui-test-packet into a stable A2A-compatible handoff_packet, prompt_packet, and artifact_refs bundle for Codex to keep refining Midscene requests. Use when the user asks for a UI-test交接协议层, prompt转换层, packet to packet mapping, failure_history preservation, retry_history preservation, or artifact reference hygiene. Do not use for real A2A transport, browser execution, or checkpoint runtime.
---

# UI-Test A2A Handoff

## Packet 3.0 handoff

From the scripts directory of the selected main UI-Test Skill run `python ui_test_suite.py a2a-handoff packet.json --output handoff.json`. To attach the bundle to a stage, supply `--project PATH --stage midscene --stage-run-id ID` in place of the output. Read the [schema](references/schema.md), [field mapping](references/mapping.md) and [boundaries](references/boundaries.md) for input checks and expected output. Return the local bundle and finish.

Both handoff_packet and prompt_packet preserve task scope, identity, risk, lineage, steps, evidence policy and handoff history. artifact_refs carries source_packet_id and refs. The main next_action uses collect-evidence for state evidence. The separate handoff.action is a suggestion. Optional review notes accept only revision_notes as a string array. Unknown history permits review and blocks retries. Only complete history with empty arrays confirms zero recorded events. Packaging reads and writes local JSON files.

## Validation

Run the bundled A2A unit tests. Verify preserved source identity, deterministic output and rejection of unsafe artifact references.

## Safety

Packaging is local and grants no execution authority. Reject credential-bearing references and attempts to override task identity or authorization in review notes.
