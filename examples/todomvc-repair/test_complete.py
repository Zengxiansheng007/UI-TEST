"""Normal project pytest node. The same source case runs before and after repair."""
from dataclasses import asdict
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from ui_test_core.asset_revision import AssetCatalog, digest, encoded, replace
from ui_test_core.artifact_layout import ProjectLayout
from ui_test_core.stage_capture import capture_step
from ui_test_core.reusable_assets import check_selected_pauses, inside, select_asset
from ui_test_core.reuse_outcome import ReuseFailure, failure_outcome
from source_case import BINDINGS, CASE, OTHER, SCOPE, TARGET, assert_rows


@pytest.mark.ui_test
@pytest.mark.r2
@pytest.mark.case_id(CASE)
@pytest.mark.branch_id("primary")
def test_two_rows(browser, ui_test_execution_context):
    from formal_result import begin
    context = ui_test_execution_context
    run = context.run_id
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,40}", run)
    project = Path(__file__).resolve().parent
    from todomvc_page import TodoPage  # Copied unchanged from the public base project during setup.
    out = ProjectLayout(project).formal_attempt(context.session_id, run)
    out.mkdir(parents=True, exist_ok=False)  # An existing attempt cannot dispatch again.
    ledger = begin(context,out)
    catalog = AssetCatalog(project)
    revision, rows = catalog.pin()
    grant = dict(scope=SCOPE, approved=True, effects=["read", "UI write"], facts=[])
    selection = select_asset(project, "script.complete", SCOPE, grant, binding=BINDINGS[CASE][0], pinned_rows=rows)
    assert selection["status"] == "selected", selection
    target_id = "locator.target"
    asset = rows[target_id]
    receipt = dict(run_id=run, case_id=CASE, attempt_ref=context.attempt_ref, scope=SCOPE, asset_id=target_id,
                   version=asset["version"], sha256=asset["sha256"], revision=revision, entered=False,
                   source_hash=digest((project/"source_case.py").read_bytes()), entries=[], writes=[],
                   action_result="not_attempted", assertion_result="unverified", step_id="COMPLETE",phase_results=ledger.rows)
    page_context = browser.new_context(service_workers="block")
    try:
        page = page_context.new_page()
        allowed = {"/todomvc/", "/todomvc/base.css", "/todomvc/index.css", "/todomvc/js/director.js", "/todomvc/js/bundle.js"}
        def restrict(route):
            url = urlsplit(route.request.url)
            if (url.scheme, url.netloc, route.request.method) == ("https", "demo.playwright.dev", "GET") and url.path in allowed and not url.query:
                route.continue_()
            else:
                route.abort()
        page.route("**/*", restrict)
        todo = TodoPage(page)
        todo.open("https://demo.playwright.dev/todomvc/")
        steps = receipt["steps"] = []
        def step_for(phase, title):
            step = dict(step_id=phase, action=title, status="failed", evidence_refs=[])
            steps.append(step)
            return step
        def capture(step, point, target, fact, ref=None):
            capture_step(page, step, context=asdict(context), run_root=out, point=point,
                         object_ref=target, observation=fact, ref=ref)
        for index, text in enumerate((OTHER, TARGET), 1):
            todo.fill(text)
            phase = ledger.phase_ids[index-1]
            step = step_for(phase, "Add " + text)
            capture(step, "pre_submit", text, "Verified title is filled")
            ledger.reserve(phase)()
            receipt["writes"].append("add")
            replace(out/"use.json", encoded(receipt))  # Reserve before the UI dispatch.
            todo.input.press("Enter")
            expect(todo.rows).to_have_count(index)
            expect(todo.rows.get_by_text(text, exact=True)).to_be_visible()
            ledger.record(phase,"write_succeeded_verified")
            capture(step, "final", text, "Matching target visible at expected row count")
            step["status"] = "passed"
        assert_rows(todo, complete=False)
        receipt["before"] = [False, False, todo.counter.inner_text()]
        step = step_for("COMPLETE", "Complete " + TARGET)
        capture(step, "pre_submit", TARGET, "Both rows are unchecked", "before.png")

        def entry(key):
            check_selected_pauses(project, selection, rows, SCOPE)  # Recheck every pinned dependency before executing code.
            row = rows[key]
            frozen = inside(project, row["recovery_source"])
            source = frozen.read_bytes()
            assert digest(source) == row["sha256"]
            namespace = {"__name__": "project_asset"}
            exec(compile(source, str(frozen), "exec"), namespace)
            return namespace[row["symbol"].split(".")[0]]

        def ready(locator):
            component = entry("component.ready")
            receipt["entries"].append("component.ready")
            return component(locator)
        def before_check():
            check_selected_pauses(project, selection, rows, SCOPE)  # A pause during ready() must precede reservation.
            assert receipt["writes"] == ["add", "add"]
            ledger.reserve("check-target")()
            receipt["writes"].append("check")
            receipt["action_result"] = "unknown"
            replace(out/"use.json", encoded(receipt))
        try:
            target = entry(target_id)(todo, TARGET).row
            receipt.update(entered=True, matches=target.count())
            receipt["entries"].append(target_id)
            script = entry("script.complete")
            receipt["entries"].append("script.complete")
            script(ready, target, before_check)
        except ReuseFailure as error:
            assert_rows(todo, complete=False)  # The failed lookup left both rows unchanged.
            result = failure_outcome(error, {**SCOPE, **asset, "asset_id": target_id})
            receipt.update(failure=result, after=[False, False, todo.counter.inner_text()])
            capture(step, "timeout", TARGET, "Both rows remain unchecked after stopped lookup", "failure.png")
            replace(out/"use.json", encoded(receipt))  # Failure precedes the scoped pause.
            if result["pause_scope"]:
                catalog.pause(target_id, asset["version"], SCOPE, expected_revision=revision)
            raise
        receipt["action_result"] = "passed"
        assert_rows(todo, complete=True)
        ledger.record("check-target","write_succeeded_verified")
        receipt.update(assertion_result="passed", after=[True, False, todo.counter.inner_text()])
        capture(step, "final", TARGET, "Only the target row is checked", "after.png")
        step["status"] = "passed"
    except Exception:
        if receipt.get("steps"):
            current = receipt["steps"][-1]
            if current["status"] == "failed" and not any(i["point"] == "timeout" for i in current.get("images", [])):
                capture(current, "timeout", current["action"], "Execution stopped before the expected result")
        raise
    finally:
        replace(out/"use.json", encoded(receipt))
        page_context.close()
