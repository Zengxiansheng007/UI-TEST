---
name: repair
description: Use when a UI asset failure is already attributed and the caller needs a scoped implementation candidate or regression verification against the original business assertion.
---

# Repair a scoped UI asset

Run `python ui_test_suite.py repair --input request.json` from the selected main Skill scripts directory. The [repair owner](scripts/__init__.py) reads the assets and committed attempt through this suite. Return the candidate or its missing prerequisites after this step.

Supply the project directory, asset_id, failure_run, exact case and environment scope, and an authorization object with approved and the same scope. Supply source_cases keyed by affected case with original project-relative source and bindings. Use the project's source-case inventory to identify dependents. For incomplete or unresolved mappings, keep the affected scope pending.

Prepare the changed implementation in a new candidate file under the project and pass its relative path as candidate_source. Keep the existing implementation, source assertions and attempt evidence. Use a project adapter for an externally owned source. The returned candidate identifies the proposed bytes, scoped version and original source hashes.

## Validation

To assess qualification, supply proof_project and proof_runs mapping each impacted case to its passing attempt in the isolated project. Inspect missing cases, result hashes and original sources before using a project's existing version activation procedure. Preserve the original project default while verification is pending. Run the targeted tests for the owner and the stage write budget.

## Safety

Return the scoped pending result for an unknown cause or write outcome. Environmental and data findings retain shared asset availability. The independent repair command reads local evidence and never allocates a business attempt. A verified candidate may be presented for the project's existing promotion procedure.
