# CR-20261127-066 Current-page checkpoint recovery

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Issue | #66 |

## Summary

Use the selected suite's checkpoint-runtime implementation for both current-page entries.

## Context And Problem

Source baseline dc304f7 had only the legacy owner and accepted previously visible features after they disappeared.

## Sections Changed

scripts-and-validation, references-and-assets.

## Decision And Alternatives

Share the readiness and identity contracts with the selected suite. The existing command and Python package resolve to the canonical implementation.

## Detailed Change

Read the live page passively, require matching scope and session, reject insufficient features and expired contexts, and return after recovery.

## Impact Analysis

Existing registry fixtures and report identities remain available. The CLI and legacy import retain their original invocation.

## Validation Evidence

The issue regression exercises both names, a local Edge page, the server submission count, expiry, session mismatch and loss of visible evidence. The original registry tests exercise dry-run and blocked requests.

## Safety And Privacy

The local test page uses synthetic values and only loopback traffic. No credentials are stored.

## Risks And Follow-up

Live external sites and private authentication are outside this controlled test.
