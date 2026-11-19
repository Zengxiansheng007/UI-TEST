import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
if os.environ.get("UI_TEST_REPAIR_SCRIPTS"):
    sys.path.insert(0, os.environ["UI_TEST_REPAIR_SCRIPTS"])
else:
    sys.path.insert(0, str(ROOT.parents[1] / "skills/ui-test/scripts"))


pytest_plugins = ("ui_test_core.pytest_runtime_plugin", "formal_result")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    options = {**browser_type_launch_args, "headless": False}
    if os.environ.get("UI_TEST_CHROMIUM"):
        options["executable_path"] = os.environ["UI_TEST_CHROMIUM"]
    return options
