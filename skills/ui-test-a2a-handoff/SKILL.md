---
name: ui-test-a2a-handoff
description: Use when an existing UI-test workflow requests the historical local Packet-to-handoff command.
---

# UI Test Handoff Compatibility

From the selected main suite’s scripts directory, run `python ui_test_suite.py ui-test-a2a-handoff` with the original packet and destination options. The existing [mapper command](scripts/a2a_handoff.py) and Python `pack` function forward to the same owner. Use `UI_TEST_SUITE` to select a relocated main Skill. Return the local bundle and finish.

## Validation

Check task identity, scope, source and artifact references in the bundle.

## Safety

A failed validation stops delivery. Packaging is local.
