---
name: ui-test-verify
description: Convert UI exploration results into deterministic Playwright verification and bounded fallback. Use when validating Midscene output, hardening recorded Playwright scripts, replacing weak locators, checking assertions, or deciding whether a UI flow can become a stable regression script.
---

# UI Test Verify compatibility entry

Resolve `verify` with the selected main suite. Forward the complete request, including recorded Playwright script hardening, evidence, action, expected outcome, risk budget and fallback limits. Follow its SKILL.md and return the same assertions, provenance, errors and bounded fallback. Preserve the requested standalone scope.

## Validation

Confirm the hardened locator and assertion against the [locator policy](references/locator-policy.md) and return the evidence for the original request.

## Safety

Preserve current-run approval, stage budgets, and stop after an unknown write outcome.
