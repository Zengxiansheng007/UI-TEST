"""Forward legacy imports and archive commands to the selected explorer."""
import os
from pathlib import Path
import runpy

configured = os.environ.get("UI_TEST_SUITE")
root = Path(configured.split(os.pathsep)[0]) if configured else Path(__file__).resolve().parents[2] / "ui-test"
root = runpy.run_path(str(root / "scripts/ui_test_suite.py"))["activate"]()
from ui_test_core.suite import selected_suite

target = selected_suite(root).skill_path("explore") / "scripts/publish_observations.py"
if __name__ == "__main__":
    runpy.run_path(str(target), run_name="__main__")
else:
    deliver = runpy.run_path(str(target))["deliver"]
