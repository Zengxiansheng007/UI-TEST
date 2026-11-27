---
name: artifact-governance
description: Use when a UI-Test project needs artifact inventory, retention preview, approval-scoped archiving and release, archive verification or isolated historical restoration.
---

# Govern UI-Test project artifacts

Select the UI-Test installation and resolve artifact-governance. Run the selected owner's scripts/project_governance.py with the project path and one requested operation. With separately installed capabilities set UI_TEST_SUITE to the selected main Skill directory. Use --help for command arguments. Return each operation's receipt or blocked reasons to its caller.

## Safety and operating rules

1. Use inventory to identify stage originals, version bindings and consumers. Run-catalog supplies historical run identity and the actual bound version. Assets supplies current effective revisions and declarations. Inspect shared references, unresolved links and active protection before proposing release.
2. Use preview to produce the dated review list. It makes no archive or release decision. Use approve only with explicit approval for the exact preview, stages, destination and release list. Schedule changes require permission for the specific Windows task.
3. Run archive with the approval ID. Read each stage result and open verify-archive on its sealed directory. Inspect file hashes and the report, historical version, evidence and case links. Preserve source files on missing originals or a failed verification.
4. Only on authorization to release the same approved paths, run release. It rechecks current protection, consumers, verified archives and the per-file journal. Report retained paths and reasons.
5. Use restore with the stage ID and an independent destination outside project and archive. Open the recovered index, the historical script and report. Query assets separately for the currently effective revision.

## Validation

Run the entry regression in tests/test_governance_entry.py. For stage ownership, integrity checks and resumable jobs also exercise the suite's inventory, preview, archive, release and history regressions.
