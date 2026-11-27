---
name: ui-test-checkpoint-schema
description: Use when a caller requests the original ui-test-checkpoint-schema entry. Forward legacy UI-Test checkpoint validation, snapshot capture and bundling requests to checkpoint-schema in the selected suite.
---

# Checkpoint schema compatibility

Resolve `checkpoint-schema` in the selected suite and follow its instructions with the supplied arguments. The historical [CLI](scripts/checkpoint_schema.py) accepts validate, capture and bundle and preserves its Python imports. Return its result or error directly.

## Validation

The selected owner verifies both names against original command fixtures. For historical fields consult the [schema reference](references/schema.md).

## Safety

Return missing identity or scope errors before packaging. This offline operation uses existing evidence.
