# CR-20261120-031 · 原始事务与未知执行接续

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Change Type | fixed |
| Scope | scripts-and-validation, safety-and-governance, references-and-assets |
| Source | UI-TEST #22 integration review |
| Baseline | fd07e04e2b77b578236390548405df875d4e568c |
| Author | Codex |
| Related Records | CR-20261120-025, CR-20261120-029 |

## Summary

ui-test core verifies the owner-bound transaction and node identity. The dispatcher retains an unknown run, waits for physical process exit and applies its serial scopes and concrete conflicts to later nodes. Both modes recheck a cached pass on re-entry. Concrete serial scopes now appear with the decision reference.

## Context And Problem

An intact copied receipt masked damage to business evidence. Refusal of a duplicate delivery overwrote the missing result of the running owner. An unknown independent node blocked the following wave after its process exited.

## Sections Changed

Session evidence, execution attempt store, transaction reader, serial and parallel dispatch, and regression tests.

## Decision And Alternatives

Reopen the immutable manifest, both content-addressed objects and original receipt. Use exact owner binding for local business roots. Portable bundles carry the complete transaction under runs/<run_id>. No recursive discovery or business reruns are required.

## Detailed Change

ui-test core verifies the owner-bound transaction and node identity. The dispatcher retains an unknown run, waits for physical process exit and applies its serial scopes and concrete conflicts to later nodes. Both modes recheck a cached pass on re-entry. Concrete serial scopes now appear with the decision reference.

## Impact Analysis

Existing read-only and qualification terminals retain their declared semantics. Older projects with conventional case directories can be verified with their original owner marker and execution context. Unknown physical exit still prevents the next wave.

## Validation Evidence

Local evidence is in `c22-evidence/final-review`. The source trees for both skills are pinned in `skill-baselines.txt`. The initial reproductions are in `red.xml`; the focused suites and final candidate checks are recorded alongside them.

The first nine checks recorded eight failures and one existing guard. The thirteen focused checks in `candidate.xml` passed. They cover malformed originals, archive closure, refusal after setup, concrete scope notices, independent progress, accepted-conflict protection, cached pass revalidation and the offline report. Both `--require-change-records` validators returned zero findings. A broader first run exceeded the runner's five-minute limit; its partial output remains in `green.xml` and the rerun uses `suite.xml`.

Review of `c005925` found the owner could crash before its setup report reached the controller. The duplicate refusal establishes that an owner existed. Without a delivered run ID the controller preserves the unknown disposition and omits the unconfirmed identity. The second review also exercised a relocated pre-locator archive. Its local `runs/<run_id>` closure supplies the original transaction and an incomplete archive stays incomplete. The two failures are in `r2-red.xml`. The 18 passing checks in `r2-focused.xml` include the real two-worker setup crash, both generations of portable bundles and registry validation. The package baseline now records 284 tracked files and the existing SKILL.md digest.

## Safety And Privacy

Follow-up on `b22fe8f` distinguished a closed owner in a previous session from a crashed owner in the current session. A refused delivery with only its teardown stays unexecuted; the controller needs a reported run ID or a node-specific worker crash to preserve an unknown original. Historical archives verify their own transaction tree. A missing tree can reach sibling runs only at the original standard project evidence root, with matching project configuration and owner digests. The regression evidence is in `r3-red.xml`, `r3-archive-red.xml`, `r3-focused.xml` and `r3-source-sessions.json`.

The regressions use disposable evidence. Scope notices contain the existing decision reference and selected node IDs.

## Risks And Follow-up

This review covers offline evidence readers and synthetic scheduler runs. The original #30 business artifacts retain their original commits and timestamps.
