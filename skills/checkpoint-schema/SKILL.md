---
name: checkpoint-schema
description: Validate, bundle, and review UI-test checkpoint schema artifacts for staged exploration and reusable regression promotion. Use for stage 2.2 checkpoint packets, CP0-CP6 granularity, checkpoint evidence readiness, staleness policy, promotion gates, and checkpoint bundle validation.
---

# UI-Test Checkpoint Schema

## Purpose

This skill packages the stage 2.2 checkpoint schema contract. It validates checkpoint artifacts, builds checkpoint bundles, and decides whether a UI flow segment can be reused without repeating earlier Midscene exploration.

## Operating Rules

- Checkpoint granularity is business-subchain level, not individual click/input level.
- Use CP0-CP6 as the default stage set: governance baseline, login state, project switch, module entry, page/modal open, form fill, submit/result verification.
- Preserve dependencies between checkpoints.
- A checkpoint is reusable only when validation, evidence, governance, promotion gate, and staleness policy are satisfied.
- Write checkpoints require cleanup policy and explicit safety approval.
- Failed, degraded, or blocked checkpoints require failure attribution.

## Workflow

Run the selected main Skill CLI from its scripts directory. Set `$fixtures` to the absolute path of this capability’s fixtures directory. The [checkpoint implementation](scripts/__init__.py) handles validation and capture. Use historical 2.2 validation for inspection. Capture current Packet 3.0 task fields (steps come from the definition) and observed run facts with the reusable definition. Preserve run, session, step identities, business assertions and evidence. Observe only UI-generated traffic.

```powershell
python ui_test_suite.py checkpoint-schema capture --definition $fixtures/definition.json --task $fixtures/current_task.json --facts $fixtures/facts.json --output snapshot.json
python ui_test_suite.py checkpoint-schema bundle --input snapshot.json --output bundle.json
python ui_test_suite.py checkpoint-schema packet --input snapshot.json --output packet.json
```

Validate a reusable definition or historical 2.2 checkpoint with the same command prefix and `validate --input PATH`. Return the requested artifact or missing field names and finish. A historical snapshot retains its original session. Current browser readiness belongs to checkpoint-runtime.

The bundle contains the snapshot, derived Packet and unified A2A handoff, prompt and artifact references. See [the schema reference](references/schema.md) for historical CP0-CP6 inspection.

Definition applicability matches the supplied scope fields exactly. Each step supplies an action, risk (R0–R3), business assertion and stable step ID. The derived Packet retains per-step status and evidence references.

## Validation

Run `python -m unittest discover -s tests` from this capability directory for CLI and identity checks.

## Safety

Use redacted evidence references only. Packaging does not contact a service.
