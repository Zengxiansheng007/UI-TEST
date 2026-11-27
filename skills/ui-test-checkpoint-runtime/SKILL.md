---
name: ui-test-checkpoint-runtime
description: Use when a legacy request calls for ui-test-checkpoint-runtime through its command or Python imports. Forward the original request to the selected checkpoint-runtime capability.
---

# Checkpoint recovery compatibility

Resolve `checkpoint-runtime` in the selected UI-Test suite and follow its SKILL.md. Use the current Page and current session for read-only readiness. Preserve the original arguments, report and blocking outcome. Return after delivering that recovery result.

## Validation

Run the owner's tests for both entry names. The historical scripts/run_checkpoint_runtime.py and checkpoint_runtime Python package accept the original calls. Consult [the runtime contract](references/runtime-contract.md) for registry and planning inputs.

## Safety

Apply the owner's R0/R1 and exact-action authorization boundaries.
