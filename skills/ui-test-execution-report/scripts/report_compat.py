import os
import runpy
from pathlib import Path


def runtime():
    # Legacy commands use the source distribution layout when no installed suite is selected.
    configured = os.environ.get("UI_TEST_SUITE")
    default = Path(__file__).resolve().parents[2] / "ui-test"
    first = Path(configured.split(os.pathsep)[0]) if configured else default
    launcher = first / "scripts/ui_test_suite.py"
    if not launcher.is_file():
        raise ValueError("E_SUITE_MISSING: " + str(first))
    root = runpy.run_path(str(launcher))["activate"]()
    from ui_test_core.suite import selected_suite
    return selected_suite(root)


def owner():
    return runtime().load_package("execution-report")
