# Test Plan

## Session review forward scenario

A reviewer has the two parameterized cases from a completed pytest invocation and a second invocation where a worker disappeared. Produce session reports for each from the recorded controller files, evidence roots, caller-observed exits and original batch IDs. Identify what happened to each node, which result can be used for the batch and where the reviewer can inspect the supporting terminal or receipt. Repeat after removing the controller summary in a disposable copy. Check the existing case-report example with its historical external acceptance record.

## Deterministic Tests

| Test | Command | Expected |
|---|---|---|
| Skill structure validation | `python scripts/validate_execution_report_skill.py .` | zero P0/P1 |
| Sample report generation | `python scripts/generate_report.py --input assets/sample-run.json --output-root tmp/sample-output` | three artifacts generated |
| Generated output validation | `python scripts/validate_execution_report_skill.py . --generated-root tmp/sample-output` | six UI entries, four API JSON entries, attachment index, API index |

## Acceptance Mapping

| AC | Validation |
|---|---|
| AC-016 | Count `截图缩略图（点击放大）` markers in generated HTML |
| AC-017 | Count `点击查看 JSON` markers in generated HTML |
| AC-018 | Check Chapter 5 title and absence of old evidence-wall markers |
| AC-SKILL-001 | Check generated `report.html`, `evidence-index.json`, `execution-summary.json` |
| AC-SKILL-002 | Run validator and sensitive scan |
# Screenshot Viewer Regression

- Verify viewport-sized enlargement, fit-width default, fit-window, 1:1, bounded zoom and scroll/pan.
- Verify Escape/close, focus return, background scroll restoration and reopening another image.
- Verify desktop/mobile containment and original bitmap identity.
- Verify missing images remain explicit and never render sample SVG evidence.
# Single-File Delivery Regression

- Copy only the generated HTML to an empty directory and open offline.
- Verify every embedded original SHA-256 against frozen evidence.
- Reject local/relative/network image, script, style or CSS resource dependencies.
- Confirm desktop/mobile zoom and scrolling without access to source directories.
