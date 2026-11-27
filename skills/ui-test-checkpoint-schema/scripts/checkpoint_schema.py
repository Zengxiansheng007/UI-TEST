"""Legacy CLI and import surface for the selected suite's checkpoint owner."""
import os
from pathlib import Path
import runpy
import sys


def _owner():
    configured = os.environ.get("UI_TEST_SUITE")
    root = Path(configured.split(os.pathsep)[0]) if configured else Path(__file__).resolve().parents[2] / "ui-test"
    entry = root / "scripts/ui_test_suite.py"
    if not entry.is_file():
        raise ValueError(f"E_SUITE_MISSING: {root}")
    root = runpy.run_path(str(entry))["activate"]()
    from ui_test_core.suite import selected_suite
    return selected_suite(root).load_package("checkpoint-schema")


if __name__ == "__main__":
    _owner().main()
else:
    sys.modules[__name__] = _owner()
