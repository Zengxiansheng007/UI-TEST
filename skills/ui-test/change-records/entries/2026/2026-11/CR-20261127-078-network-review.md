# CR-20261127-078 · Current response verification

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | 4003ea8 |
| Source | #57 two-repository review, P2 network verification and AC-01 |
| Author | Codex |

## Summary

Route live Page observations and pinned step records through their respective public verification entries.

## Context And Problem

The normal action entry dropped the live context. Workflow checks read UI fields alone and rejected a qualified network assertion.

## Sections Changed

The verify owner accepts live inputs and resolves recorded steps. The core observer binds redacted live context to the originating Page. Workflow delegates step verification to the selected owner.

## Decision And Alternatives

Reuse the passive observer and module readiness validation. Offline review compares the captured observation with its run, session, stage interval and step identity. Capturing another response would repeat an action and would lose provenance.

## Impact Analysis

Live and recorded checks report their source and preserve the requested assertion. UI-only checks retain their original lookup and fallback. No dispatch or write budget changes.

## Validation Evidence

The pre-change loopback test failed on the public entry's page keyword. The regression uses a real Page callback, captures GET /status from the page, consumes its observation in-process and from the pinned file, and checks session, run, step and stale-response rejection. Only GET /case and GET /status reach the fixture.

## Safety And Privacy

The test uses the local controlled page. Raw response bodies and headers are excluded from the result.

## Risks And Follow-up

Older records missing capture identity or timing report missing evidence. A digest identifies the reviewed file; the authorized input provider owns capture integrity.

## Integrated review at f02292f

Live and recorded consumers share response rule matching.

test_network_review.py passed its two live Edge and recorded delivery cases on the loopback fixture. The create-skill --require-change-records validation reported zero findings.
