---
name: script-build
description: Build a versioned formal pytest-playwright script. Use when compiling a UI source case, data and dependencies, regenerating an existing script, or reviewing its source revision.
---

# Build a formal case script

Use the selected UI-Test installation. Set PYTHONPATH to its main scripts directory. Run this Skill's [compiler](scripts/compile_project_case.py) with Python. Pass --project PROJECT --source SOURCE.json --test-data DATA.json --dependencies DEPENDENCIES.json --module-registry REGISTRY.json --display-name NAME. Use --runtime-material only for approved local compiler material. Apply exactly the exploration or selected-version basis associated with this source. Stop and identify the assertion or dependency id when material is missing.

The compiler validates each step's postconditions, binds dependencies into the release fingerprint and publishes the compiled version through the project sync coordinator. Return the active release location, playwright-test.py, manifest.json and compile-receipt.json. The caller may inspect resolved-ir.json for resolved step assertions. Submission requires the declared per-stage budgets and current-run approval at execution. An unknown result stops the write sequence. Deliver the script and return to the requester.

## Validation

Verify the compile receipt against the release manifest and referenced script. Check that no formal attempt was added.

## Safety

Never start pytest, open a browser, or retry a write while building scripts.
