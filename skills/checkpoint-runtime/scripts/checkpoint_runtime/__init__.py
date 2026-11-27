"""Locate the selected readiness owner before loading any checkpoint submodules."""
import os
from pathlib import Path
import runpy

configured = os.environ.get("UI_TEST_SUITE", "").split(os.pathsep)
root = Path(configured[0]) if configured[0] else Path(__file__).resolve().parents[3] / "ui-test"
launcher = root / "scripts/ui_test_suite.py"
if not launcher.is_file():
    raise ValueError("E_SUITE_MISSING: " + str(root))
selected = runpy.run_path(str(launcher))["activate"]()
from ui_test_core.suite import selected_suite

__path__ = [str(selected_suite(selected).skill_path("checkpoint-runtime") / "scripts/checkpoint_runtime")]
__all__ = ["__version__"]
__version__ = "0.1.0"
