"""Issue 66 verifies both entry names using a loopback page and its request ledger."""
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from playwright.sync_api import sync_playwright

SKILLS = Path(__file__).resolve().parents[2]
MAIN = SKILLS / "ui-test"
sys.path.insert(0, str(MAIN / "tests"))
from controlled_ui_page import controlled_page


@pytest.mark.parametrize("entry", ["checkpoint-runtime", "ui-test-checkpoint-runtime"])
def test_current_page_recovery(entry):
    command = [sys.executable, str(MAIN / "scripts/ui_test_suite.py"), "--suite", str(MAIN), "resolve", entry]
    resolved = subprocess.run(command, text=True, capture_output=True)
    assert resolved.returncode == 0, resolved.stderr
    assert Path(json.loads(resolved.stdout)["skill"]) == SKILLS / "checkpoint-runtime"
    sys.path.insert(0, str(SKILLS / entry / "scripts"))
    try:
        runtime = importlib.import_module("checkpoint_runtime.context")
        packet = json.loads((MAIN / "assets/fixtures/packet_valid.json").read_text())
        packet["run"]["started_at"] = datetime.now(timezone.utc).isoformat()
        with controlled_page() as (url, requests), sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            config = dict(target_url=url, module_id="checkboxes", login_selector="#identity",
                          feature_selectors=["h1", "#title"], ttl_seconds=60)
            page.goto(url)
            binding = dict(packet=packet, config=config, session_id="issue-66-current")
            ready = runtime.recover_current(page, **binding)
            assert ready["ui_features_verified"] == ["#title", "h1"]
            assert runtime.validate_context(ready, page=page, **binding)["ok"]
            yesterday = dict(ready, expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
            for snapshot, session, reason in [(yesterday, binding["session_id"], "context_expired"),
                                               (ready, "another-session", "session_mismatch")]:
                decision = runtime.validate_context(snapshot, page=page, **dict(binding, session_id=session))
                assert not decision["ok"] and decision["missing"] == reason
            page.locator("#title").evaluate("element => element.remove()")
            assert not runtime.validate_context(ready, page=page, **binding)["ok"]
            with pytest.raises(ValueError, match="SIGNATURE_INSUFFICIENT"):
                runtime.recover_current(page, **binding)
            assert requests.count(("POST", "/submit")) == 0
            print(entry, ready["context_id"], ready["ui_features_verified"], requests)
            browser.close()
    finally:
        sys.path.pop(0)
        for name in list(sys.modules):
            if name == "checkpoint_runtime" or name.startswith("checkpoint_runtime."):
                del sys.modules[name]
