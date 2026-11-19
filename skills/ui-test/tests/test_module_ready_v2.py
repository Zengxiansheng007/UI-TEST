import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ui_test_core.checkpoint_governance import verify_module_signature

class ReadyEvidenceTests(unittest.TestCase):
    def test_missing_host_and_login_block_two_features(self):
        self.assertFalse(verify_module_signature(True, ["title", "list"])["ok"])

    def test_bare_reference_does_not_prove_business_success(self):
        result = verify_module_signature(True, ["title"], "response-1", host_verified=True, authenticated_session_verified=True)
        self.assertFalse(result["ok"])

class VisibleReadinessTests(unittest.TestCase):
    def test_checkpoint_and_exploration_use_current_page(self):
        import json
        from pathlib import Path
        import sys
        from datetime import datetime, timezone, timedelta
        from playwright.sync_api import sync_playwright
        from controlled_ui_page import controlled_page
        from scripts.ui_test_core.automation_runtime import exploration_entry_decision
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root.parent / "ui-test-checkpoint-runtime" / "scripts"))
        from checkpoint_runtime.context import capture_context, validate_context
        packet = json.loads((root / "assets/fixtures/packet_valid.json").read_text())
        packet["run"]["started_at"] = datetime.now(timezone.utc).isoformat()
        with controlled_page() as (url, requests), sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=False)
            page = browser.new_page()
            config = dict(target_url=url, login_selector="#identity", feature_selectors=["h1", "#result", "#title"],
                          module_id="checkboxes", ttl_seconds=60)
            def enter(active):
                active.goto(url)
            def capture(action=enter):
                return capture_context(page, packet=packet, session_id="s", config=config, enter=action)
            def decide(ctx):
                return exploration_entry_decision(module_ready_context=ctx, current_session_id="s",
                         current_run_id=packet["run"]["run_id"], formal_playwright=False, packet=packet, page=page, config=config)
            first = capture()
            self.assertEqual(decide(first)["mode"], "checkpoint-direct-route")
            from scripts.ui_test_core.midscene_adapter import MidsceneAdapter
            adapter = MidsceneAdapter()
            binding = dict(page=page, packet=packet, config=config, session_id="s")
            self.assertTrue(adapter.preflight("1.17.7", True, first, **binding)["ok"])
            progress = []
            adapter.explore(context=first, intent="controlled assertion", executor=lambda **_: {"status":"passed"},
                            progress=progress.append, **binding)
            self.assertEqual([item["event"] for item in progress], ["started","finished"])
            for changed in (url + "/other", url.replace("127.0.0.1", "localhost")):
                wrong_target = dict(config, target_url=changed)
                self.assertFalse(validate_context(first, page=page, packet=packet, session_id="s", config=wrong_target)["ok"])
            other_task = dict(packet, case={"case_id":"different"})
            self.assertFalse(validate_context(first, page=page, packet=other_task, session_id="s", config=config)["ok"])
            config["feature_selectors"] = ["h1","body h1"]
            with self.assertRaises(ValueError):
                capture()
            config["response"] = dict(path="/submit", method="POST", success_field="saved")
            def submit(active):
                active.goto(url)
                active.locator("#title").fill("local")
                active.locator("#submit").click()
                active.get_by_text("Saved",exact=True).wait_for()
            second = capture(submit)
            self.assertTrue(validate_context(second, page=page, packet=packet, config=config, session_id="s")["ok"])
            self.assertEqual(decide(second)["mode"], "checkpoint-direct-route")
            self.assertFalse(validate_context(second, page=page, packet=packet, config=config, session_id="other")["ok"])
            expired = dict(second,expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
            self.assertEqual(decide(expired)["mode"], "semantic-menu-exploration")
            page.locator("#identity").evaluate("e => e.remove()")
            self.assertEqual(decide(second)["mode"], "semantic-menu-exploration")
            config["response"]["path"] = "/unrelated"
            with self.assertRaises(ValueError):
                capture(submit)
            config["response"]["path"] = "/submit"
            def rejected(active):
                active.goto(url)
                active.locator("#submit").click()
                active.get_by_text("Rejected",exact=True).wait_for()
            with self.assertRaises(ValueError):
                capture(rejected)
            def succeeded_then_failed(active):
                submit(active)
                active.locator("#title").fill("")
                active.locator("#submit").click()
                active.get_by_text("Rejected", exact=True).wait_for()
            with self.assertRaises(ValueError):
                capture(succeeded_then_failed)
            self.assertEqual(requests.count(("POST","/submit")), 5)
            browser.close()

    def test_visible_checkpoint_cli(self):
        import json
        import os
        import shutil
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from controlled_ui_page import controlled_page
        root = Path(__file__).resolve().parents[1]
        runtime = root.parent / "ui-test-checkpoint-runtime"
        with controlled_page() as (url, requests), tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            box = base / "registry"
            shutil.copytree(runtime / "assets/fixtures/runtime-root", box)
            manifest = box / "systems/demo-system/modules/requirement-pool/module.manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data.update(base_url=url, module_ready=dict(login_selector="#identity",feature_selectors=["h1","#title"],ttl_seconds=60))
            manifest.write_text(json.dumps(data),encoding="utf-8")
            packet = json.loads((root / "assets/fixtures/packet_valid.json").read_text())
            packet["scope"].update(project_group="public-pilot",product="public-ui",system="demo-system",
                                   module_path=["requirement-pool"],function="module-entry",checkpoint="CP3-module-entry",environment="test")
            source, output = base/"packet.json", base/"report.json"
            source.write_text(json.dumps(packet),encoding="utf-8")
            cli = subprocess.run([sys.executable,str(runtime/"scripts/run_checkpoint_runtime.py"),"--root",str(box),
                                  "--system-id","demo-system","--module-id","requirement-pool","--environment-alias","test",
                                  "--ready-packet",str(source),"--report",str(output),"--mode","live-public",
                                  "--session-id","session-local","--run-id",packet["run"]["run_id"]],
                                 env={**os.environ,"UI_TEST_BROWSER_CHANNEL":"msedge"},capture_output=True,text=True,timeout=60)
            self.assertEqual(cli.returncode,0,cli.stderr)
            ready = json.loads(output.read_text(encoding="utf-8"))["module_ready_context"]
            self.assertEqual(ready["schema_version"],"2.0")
            self.assertEqual(ready["scope"],packet["scope"])
            self.assertEqual(ready["ui_features_verified"],["#title","h1"])
            self.assertEqual(requests.count(("GET","/case")),1)

if __name__ == "__main__":
    import sys
    from pathlib import Path
    if unittest.main(exit=False).result.wasSuccessful():
        print("Visible checkpoint and exploration readiness assertions passed.")
    else:
        sys.exit(1)
