"""A response belongs to the page session whose user action produced it."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from playwright.sync_api import sync_playwright

CORE = Path(__file__).resolve().parents[2] / "ui-test"
sys.path.insert(0, str(CORE / "scripts"))
sys.path.insert(0, str(CORE / "tests"))
from controlled_ui_page import controlled_page
from ui_test_core.suite import selected_suite
from ui_test_core.workflow import verify_checks


def test_current_response_through_verify_owner(tmp_path):
    from importlib import import_module
    owner = selected_suite(CORE).load_package("verify")
    review = import_module(owner.__name__ + ".review_action").review_action
    packet = json.loads((CORE / "assets/fixtures/packet_valid.json").read_bytes())
    packet["run"]["started_at"] = datetime.now(timezone.utc).isoformat()
    with controlled_page() as (url, requests), sync_playwright() as driver:
        browser = driver.chromium.launch(channel="msedge")
        page = browser.new_page()
        page.route("**/*", lambda route: route.continue_() if route.request.url in (
            url, url.replace("/case", "/status")) else route.abort())
        config = dict(target_url=url, module_id="local", login_selector="#identity",
                      feature_selectors=["h1", "#title"], ttl_seconds=180,
                      response=dict(method="GET", path="/status", success_field="ready"))
        binding = dict(page=page, packet=packet, config=config, session_id="current")
        def read_status(current_page):
            assert current_page is page
            current_page.goto(url)
            current_page.locator("#status").click()
            current_page.get_by_text("Available", exact=True).wait_for()

        checkpoint = selected_suite(CORE).load_package("checkpoint-runtime")
        capture = import_module(checkpoint.__name__ + ".checkpoint_runtime.context").capture_context
        binding["ready_context"] = capture(**binding, enter=read_status)
        ref = binding["ready_context"]["readonly_network_evidence_ref"]
        action = dict(action="Read current status", evidence_ref=ref, observed={},
                      expected={"network_readonly": ref})
        assert review(action, **binding)["status"] == "passed"
        other = browser.new_page()
        document = page.content()
        other.route("**/*", lambda route: route.fulfill(body=document, content_type="text/html"))
        other.goto(url)
        assert review(action, **dict(binding, page=other))["primary"]["code"] == "E_CURRENT_NETWORK_EVIDENCE_MISSING"
        for changed in (dict(session_id="other"), dict(packet=dict(packet, run={"run_id": "other"})),
                        dict(config=dict(config, response=dict(config["response"], path="/other")))):
            assert review(action, **dict(binding, **changed))["primary"]["code"] == "E_CURRENT_NETWORK_EVIDENCE_MISSING"
        context = binding["ready_context"]
        owner = dict(run_id=context["run_id"], case_id=packet["case"]["case_id"], branch_id=packet["branch"]["branch_id"],
                     attempt_ref="1", step_id="read", session_id=binding["session_id"])
        fact = dict(context["network_evidence"], **owner)
        step = dict(action=action["action"], step_id="read", network_evidence=fact)
        observations = dict(run_id=owner["run_id"], stage="midscene", session_id=owner["session_id"],
                            started_at=packet["run"]["started_at"], ended_at=context["generated_at"],
                            cases=[dict(case_id=owner["case_id"], branch_id=owner["branch_id"], run_id=owner["run_id"],
                                        attempt_ref="1", status="observed", steps=[step])])
        check = dict(expected=action["expected"], **owner)
        suite = selected_suite(CORE)
        def stored():
            result, = verify_checks(suite, observations, [check])
            return result["primary"]

        assert stored()["checks"][0]["mode"] == "recorded" and stored()["passed"]
        source = tmp_path / "check.json"
        source.write_text(json.dumps(check))
        artifact = tmp_path / "observations.json"
        artifact.write_text(json.dumps(observations))
        args = [sys.executable, str(CORE.parent / "verify/scripts/review_action.py"), "--input", str(source),
                "--observations", str(artifact), "--observations-sha256", hashlib.sha256(artifact.read_bytes()).hexdigest()]
        env = dict(os.environ, UI_TEST_SUITE=str(CORE), PYTHONPATH=str(CORE / "scripts"))
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["primary"] == stored()
        artifact.write_text("{}")
        assert "E_CURRENT_NETWORK_EVIDENCE_MISSING" in subprocess.run(
            args, env=env, capture_output=True, text=True, timeout=45).stderr
        for changed in (dict(session_id="other"), dict(run_id="other"), dict(step_id="other"),
                        dict(attempt_ref="2"), dict(source="model"), dict(business_success=False), dict(status=409),
                        dict(observed_at="2000-01-01T00:00:00Z")):
            step["network_evidence"] = dict(fact, **changed)
            assert stored()["code"] == "E_CURRENT_NETWORK_EVIDENCE_MISSING"
        step.pop("network_evidence")
        step["observed"] = {"network_readonly": ref}
        assert stored()["code"] == "E_CURRENT_NETWORK_EVIDENCE_MISSING"
        assert requests == [("GET", "/case"), ("GET", "/status")]
        browser.close()
