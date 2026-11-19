---
name: ui-test-evidence
description: Build Solution D evidence indexes for UI automation. Use when collecting screenshots, current-session page responses, contract checks, visible task state and downstream UI results.
---

# UI Test Evidence

## Purpose

Collect and normalize evidence so humans and Codex can determine what really happened.

## Operating Rules

- Page success, API success, task success, and downstream success are different evidence layers.
- Preserve every step's evidence reference. Do not hide duplicate screenshots; mark them as repeated visual state.
- Capture screenshots for UI-changing steps and all browser-visible failures.
- Consume the current run and session's redacted page-response evidence. If it is unavailable, record an equivalent visible UI assertion or the missing evidence. Collection must never initiate a request, poll an endpoint or replay traffic.
- Persist only redacted summaries. Exclude credentials, cookies, authorization headers and raw response bodies even for controlled runs.
- Consume canonical RunResult and preserve its run/case/branch/step lineage. Evidence cannot change overall status.
- Store execution evidence under the governed `D:\UI-Test` run path and only redacted evidence indexes under the configured `D:\RAG` knowledge space.
- Reject formal C-drive references and root/type mismatches; ordinary non-UI-Test workspace files are outside this rule.

## Workflow

1. Consume a validated Packet 3.0 with `next_action: collect-evidence`. Preserve lifecycle state `evidence` and build an evidence index from run artifacts.
2. Classify each artifact by step, layer, type, timestamp, sensitivity, and consumer.
3. Attach failure attribution with layer, root cause, confidence, evidence refs, impact scope, action taken, and next step.
4. Generate Codex-readable JSON and human-readable HTML references when required.
5. Output `next_action: review`.

## Validation

- Each executed step has evidence or an explicit missing-evidence reason.
- Failure evidence is enough to distinguish business defect, test asset problem, environment-data issue, requirement ambiguity, AI recognition failure, policy block, or unknown.
- Sensitive data handling is recorded.

Read [the evidence taxonomy](references/evidence-taxonomy.md) before classifying cross-layer evidence.

## Safety

Do not persist credentials, authentication state, raw private endpoints, or unredacted business identifiers. Evidence collection cannot authorize a write or change canonical RunResult status.
