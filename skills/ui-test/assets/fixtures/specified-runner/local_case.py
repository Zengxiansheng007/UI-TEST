import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

import pytest
from playwright.sync_api import sync_playwright

from scripts.ui_test_core.case_contracts import canonical_hash
from scripts.ui_test_core.execution_data_session import ExecutionDataSession
from scripts.ui_test_core.module_ready import ModuleReadyObserver, consume_ready_context

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
from controlled_ui_page import controlled_page


@pytest.mark.ui_test
@pytest.mark.case_id("CASE-LOCAL")
@pytest.mark.branch_id("main")
@pytest.mark.r2
def test_single_submit(ui_test_execution_context):
    run_case(ui_test_execution_context)


@pytest.mark.ui_test
@pytest.mark.case_id("CASE-STAGED")
@pytest.mark.branch_id("main")
@pytest.mark.r2
def test_staged_submit(ui_test_execution_context):
    run_case(ui_test_execution_context)


def run_case(ctx):
    budget = ctx.config_summary.get("stage_write_budget")
    phases = budget["phase_ids"] if budget else [None]
    root = Path(os.environ["CONTROLLED_UI_EVIDENCE"]) / "runs" / ctx.run_id
    root.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": "ui-test.test-data.v2", "case_id": ctx.case_id, "branch_id": ctx.branch_id,
            "data_revision": 1, "parameters": {"title": "Local case"}, "generation_rules": {},
            "runtime_refs": [], "metadata": {}}
    data_path = root / "test-data.json"
    data_path.write_text(json.dumps(data))
    manifest = {"case_id": ctx.case_id, "branch_id": ctx.branch_id, "test_data_hash": canonical_hash(data),
                "parameters": [{"parameter_id": "title", "ref": "test-data:/parameters/title",
                                "source_type": "test-data", "value": "Local case"}]}
    manifest["parameter_manifest_hash"] = canonical_hash(manifest)
    session = ExecutionDataSession(run_id=ctx.run_id, build_fingerprint=ctx.runner_digest,
                                   test_data_path=data_path, parameter_manifest=manifest, stage_write_budget=budget)
    session.start()
    session.seal_snapshot(root / "snapshot.json")
    boundary = {"run_id": ctx.run_id, "case_id": ctx.case_id, "environment": ctx.environment,
                "allowed_action": ctx.branch_id, "channel": "visible-ui", "max_submit_count": len(phases)}
    approval = {**boundary, "schema_version": "ui-test.r2-approval-record.v3",
                "approval_id": ctx.run_id + "-approval", "approval_source": ctx.approval_source,
                "node_id": ctx.node_id, "branch_id": ctx.branch_id, "decision": "approved",
                "boundary_hash": canonical_hash(boundary), "credential_values_persisted": False,
                "reusable_across_runs": False, "risk_level": ctx.risk_level, "runner_digest": ctx.runner_digest}
    if budget:
        approval["stage_write_budget"] = budget
    assert ctx.approved
    (root / "approval.json").write_text(json.dumps(approval))
    with controlled_page() as (url, requests), sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=False)
        try:
            page = browser.new_page()
            expected_url = os.environ.get("CONTROLLED_UI_EXPECTED_URL", url)
            packet = {
                "scope": {"project_group": "local-fixture", "product": "controlled-ui", "system": "fixture",
                          "module_path": ["fixture-core"], "function": "create-fixture", "checkpoint": "entry",
                          "environment": ctx.environment, "risk_level": "r1-read-only-authenticated"},
                "run": {"run_id": ctx.run_id, "started_at": datetime.now(timezone.utc).isoformat()},
                "case": {"case_id": ctx.case_id}, "branch": {"branch_id": ctx.branch_id},
                "schema_version": "3.0", "packet_type": "ui-test-packet", "packet_id": ctx.run_id + "-ready",
                "risk_level": "r1-read-only-authenticated", "state": "plan", "next_action": "validate",
                "steps": [{"step_id": "ready", "action": "assert", "risk_level": "r1-read-only-authenticated",
                           "required": True, "intent": "Verify local module readiness", "postcondition": "Two visible features"}],
                "objective": "Observe local fixture readiness", "artifact_refs": ["local_case.py"],
                "lineage": {"anchor_id": ctx.case_id, "source_refs": ["local_case.py"]},
                "evidence_policy": {"screenshot_on_ui_change": True, "redaction_required": True},
                "retry_policy": {"max_attempts": 1, "fallback_allowed": False},
                "handoff": {"action": "review", "constraints": ["Observe local page"], "history_status": "complete",
                            "failure_history": [], "retry_history": [], "required_fix_points": []},
            }
            config = dict(target_url=expected_url, login_selector="#identity", feature_selectors=["h1", "#title"],
                          module_id="fixture-core", ttl_seconds=60)
            observer = ModuleReadyObserver(page, packet=packet, session_id=ctx.session_id, config=config)
            try:
                page.goto(url)
                assert page.url == expected_url, "E_CONTROLLED_TARGET_MISMATCH"
                ready = observer.capture()
            finally:
                observer.close()
            assert consume_ready_context(ready, page=page, packet=packet, session_id=ctx.session_id, config=config)["ok"]
            (root / "module-ready.json").write_text(json.dumps(ready), encoding="utf-8")
            assert page.locator("#identity").inner_text() == "Signed in as local tester"
            try:
                for index, phase in enumerate(phases):
                    assert requests.count(("POST", "/submit")) == index
                    assert page.locator("#result").inner_text() == ("Saved" if index else "")
                    value = data["parameters"]["title"] + (f" {phase}" if phase else "")
                    page.locator("#title").fill(value)
                    assert page.locator("#title").input_value() == value
                    permit = session.authorize_business_write(phase)
                    with page.expect_response(lambda r: r.url.endswith("/submit") and r.request.method == "POST") as observed:
                        permit.consume()
                        page.locator("#submit").click()
                    assert observed.value.request.post_data == value
                    assert observed.value.json()["saved"]
                    page.get_by_text("Saved", exact=True).wait_for()
                    assert requests.count(("POST", "/submit")) == index + 1
                    session.record_business_write_result(phase, "write_succeeded_verified")
                page.screenshot(path=str(root / "saved.png"))
            finally:
                rows = session.phase_results
                attempted = [row for row in rows if row["submit_count"]]
                (root / "observed.json").write_text(json.dumps({
                    "submit_count": len(attempted), "phase_results": rows,
                    "write_state": attempted[-1]["write_state"] if attempted else "not_attempted",
                    "requests": requests,
                }))
        finally:
            browser.close()

