"""A reviewed UI-triggered GET complements one independent UI feature."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "ui-test/tests"))
sys.path.insert(0, str(SKILLS / "checkpoint-runtime/scripts"))
from controlled_ui_page import controlled_page
from checkpoint_runtime.context import capture_context, validate_context


def test_natural_read_with_one_feature():
    packet = json.loads((SKILLS / "ui-test/assets/fixtures/packet_valid.json").read_text())
    packet["run"]["started_at"] = datetime.now(timezone.utc).isoformat()
    with controlled_page() as (url, requests), sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        page.goto(url)
        config = dict(target_url=url, module_id="checkboxes", login_selector="#identity", feature_selectors=["h1"],
                      ttl_seconds=60, response=dict(method="GET", path="/status", success_field="ready"))
        binding = dict(packet=packet, config=config, session_id="session-natural-read")

        def check_status(active):
            active.locator("#status").click()
            active.get_by_text("Available", exact=True).wait_for()

        ready = capture_context(page, **binding, enter=check_status)
        assert ready["network_evidence"]["business_success"]
        assert ready["ui_features_verified"] == ["h1"]
        assert validate_context(ready, page=page, **binding)["ok"]
        assert requests.count(("GET", "/status")) == 1
        assert requests.count(("POST", "/submit")) == 0
        print("natural-read", ready["context_id"], requests)
        browser.close()
