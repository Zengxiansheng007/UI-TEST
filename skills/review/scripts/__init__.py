"""Explain recorded UI failures without rerunning or changing an assertion."""
from pathlib import Path

from ui_test_core.strict_json import loads_strict
from ui_test_core.suite import selected_suite


# A timeout or a denied action alone cannot identify which component caused it.
CAUSES = {
    "locator_drift": ("asset", "Compare the recorded locator with this page version."),
    "stale_source": ("asset", "Inspect the exact source or script version in this attempt."),
    "data_stale": ("data", "Verify the fixture version and validity at execution time."),
    "browser_disconnected": ("environment", "Check the browser and runner connection for this attempt."),
    "environment_unavailable": ("environment", "Verify the environment prerequisite at the recorded step."),
    "business_assertion_mismatch": ("business", "Compare the business expectation with the recorded UI result."),
}
UNKNOWN = ("unknown", "Inspect the original assertion, page state, data and asset version before assigning a cause.")


def review_file(source, *, run_root=None, original=None):
    """An index can only point to the observations it actually projects."""
    evidence = selected_suite().load_package("evidence")
    source = Path(source)
    supplied = loads_strict(source.read_bytes().decode("utf8"))
    if supplied.get("schema_version") == evidence.VERSION:
        if original is None:
            name = evidence.safe_identity(supplied.get("source_name"))
            if Path(name).name != name or ":" in name:
                raise ValueError("E_REVIEW_ORIGINAL_REQUIRED")
            original = source.parent / name
            if original.resolve().parent != source.parent.resolve():
                raise ValueError("E_REVIEW_ORIGINAL_REQUIRED")
        index = evidence.build_index(original, run_root=run_root)
        if index != supplied:
            raise ValueError("E_REVIEW_ORIGINAL_MISMATCH")
    else:
        index = evidence.build_index(source, run_root=run_root)
    findings = []
    for step in index["steps"]:
        if step["status"] in {"passed", "observed", "not-executed", "not_executed"}:
            continue
        category, scope = CAUSES.get(step["diagnostic"], UNKNOWN)
        findings.append({**{k: step[k] for k in evidence.IDENTITY}, "category": category, "scope": scope,
                         "basis": {"source_pointer": step["pointer"], "status": step["status"],
                                   "recorded_diagnostic": step["diagnostic"]},
                         "confidence": "recorded-diagnostic" if category != "unknown" else "insufficient-evidence"})
    return {"schema_version": "ui-test.step-review.v1", "source_sha256": index["source_sha256"],
            "source_name": index["source_name"], "findings": findings}
