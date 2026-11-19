import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ui_test_core.verifier import verify_postcondition
from scripts.ui_test_core.retry_policy import retry_scope_for_action


class PassiveVerificationTests(unittest.TestCase):
    def test_unbound_network_claim_is_insufficient(self):
        result = verify_postcondition({"network_readonly": True}, {"network_readonly": True})
        self.assertFalse(result["passed"])

    def test_query_cannot_be_retried(self):
        for action in ("submit", "read"):
            self.assertFalse(retry_scope_for_action(action, "post-submit-query")["retry_allowed"])

    def test_ui_failure_keeps_diagnostic_without_credentials(self):
        import json
        from urllib.parse import urlencode
        from uuid import uuid4
        private_query_value = uuid4().hex
        url = "/?" + urlencode({"token": private_query_value})
        result = verify_postcondition({"url": url, "input_value": "sensitive-password"},
                                      {"url": "/elsewhere", "input_value": "expected-password"})
        self.assertFalse(result["passed"])
        self.assertEqual([check["field"] for check in result["checks"]], ["url", "input_value"])
        for marker in (private_query_value, "sensitive-password", "expected-password"):
            self.assertNotIn(marker, json.dumps(result))

    def test_controlled_verification_evidence_fallback_and_recovery(self):
        from datetime import datetime, timezone
        import json
        from playwright.sync_api import sync_playwright
        from controlled_ui_page import controlled_page
        from scripts.ui_test_core.module_ready import ModuleReadyObserver, consume_ready_context
        from scripts.ui_test_core.retry_policy import record_fallback

        root = Path(__file__).resolve().parents[1]
        packet = json.loads((root / "assets/fixtures/packet_valid.json").read_text())
        packet["run"]["started_at"] = datetime.now(timezone.utc).isoformat()
        tools = []

        def call(name, function, *args, **kwargs):
            tools.append(name)
            return function(*args, **kwargs)

        headers = [("Set-Cookie", "test=private-cookie"), ("Authorization", "private-auth"),
                   ("X-Session-Token", "private-session")]
        with controlled_page(response_headers=headers) as (url, requests), sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=False)
            page = browser.new_page()
            config = dict(target_url=url, module_id="local", login_selector="#identity",
                          feature_selectors=["h1", "#title"], ttl_seconds=60,
                          response=dict(method="GET", path="/status", success_field="ready"))
            binding = dict(packet=packet, session_id="test-session", config=config)
            observer = call("attach-page-listener", ModuleReadyObserver, page, **binding)
            call("goto-case", page.goto, url)
            call("click-check-status", page.locator("#status").click)
            call("wait-visible-result", page.get_by_text("Available", exact=True).wait_for)
            context = call("collect-evidence", observer.capture)
            expected = {"network_readonly": context["readonly_network_evidence_ref"]}
            good = call("verify", verify_postcondition, {}, expected, ready_context=context, page=page, **binding)
            self.assertTrue(good["passed"])
            for changed in ({"path": "/other"}, {"method": "POST"}, {"success_field": "other"}):
                wrong = dict(config, response={**config["response"], **changed})
                rejected = call("reject-unrelated-response", verify_postcondition, {}, expected,
                                ready_context=context, page=page, **dict(binding, config=wrong))
                self.assertFalse(rejected["passed"])
            bad = call("verify-missing-reference", verify_postcondition, {}, {"network_readonly": "missing"},
                       ready_context=context, page=page, **binding)
            self.assertFalse(bad["passed"])
            visible = call("read-visible-result", page.locator("#result").inner_text)
            alternate = call("verify-ui", verify_postcondition, {"visible_text": [visible]}, {"visible_text": ["Available"]})
            fallback = call("record-fallback", record_fallback, reason=bad["code"], changed_variable="evidence",
                            scope="post-submit-assertion", result=alternate["status"], attempt=1)
            self.assertEqual(fallback["result"], "passed")
            self.assertNotEqual(fallback["reason"], "OK")
            self.assertTrue(call("recover-current-session", consume_ready_context, context, page=page, **binding)["ok"])
            stale = dict(binding, session_id="another")
            self.assertFalse(call("reject-stale-recovery", consume_ready_context, context, page=page, **stale)["ok"])
            browser.close()
            self.assertEqual([r for r in requests if r != ("GET", "/favicon.ico")],
                             [("GET", "/case"), ("GET", "/status")])
            record = dict(server=requests, tools=tools, failed_check=bad, fallback=fallback, evidence=context)
            self.assertNotIn("private-fixture-value", json.dumps(record))
            for _, value in headers:
                self.assertNotIn(value, json.dumps(record))
            print(json.dumps(record), file=sys.stderr)

    def test_checkpoint_runner_retains_only_redacted_network_metadata(self):
        import json
        import os
        import subprocess
        import tempfile
        from controlled_ui_page import controlled_page
        root = Path(__file__).resolve().parents[2]
        runner = root / "ui-test-checkpoint-runtime/scripts/checkpoint_runtime/playwright_runner.cjs"
        headers = [("Set-Cookie", "test=private-cookie"), ("X-Api-Key", "private-key")]
        with controlled_page(response_headers=headers) as (url, requests), tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            payload = dict(module_assertions=dict(title_contains="Controlled", url_contains="/case",
                                                  visible_text="Signed in as local tester"),
                           before_screenshot="page.png", output_path="result.json")
            (base / "input.json").write_text(json.dumps(payload))
            command = subprocess.run(["node", str(runner), "input.json"], cwd=base, timeout=60,
                                     env={**os.environ, "CHECKPOINT_RUNTIME_BASE_URL": url,
                                          "UI_TEST_BROWSER_CHANNEL": "msedge"})
            self.assertEqual(command.returncode, 0)
            result = json.loads((base / "result.json").read_text())
            self.assertEqual(result["result"], "passed")
            self.assertTrue(result["responses"])
            self.assertEqual([r for r in requests if r != ("GET", "/favicon.ico")], [("GET", "/case")])
            self.assertFalse(list(base.glob("*.zip")))
            for response in result["responses"]:
                self.assertNotIn("headers", response)
                self.assertNotIn("path", response)
            for _, value in headers:
                self.assertNotIn(value, json.dumps(result))
            print(json.dumps(dict(checkpoint_requests=requests, responses=result["responses"])), file=sys.stderr)


if __name__ == "__main__":
    if not unittest.main(exit=False).result.wasSuccessful():
        sys.exit(1)
    print("Passive network assertions passed.")
