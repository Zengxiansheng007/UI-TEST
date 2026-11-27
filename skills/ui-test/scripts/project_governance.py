"""Run the selected suite's project governance command with the original arguments."""
from importlib import import_module
import os
from pathlib import Path
import runpy


def main():
    configured = os.environ.get("UI_TEST_SUITE", "").split(os.pathsep)
    root = Path(configured[0]) if configured[0] else Path(__file__).resolve().parents[1]
    launcher = root / "scripts/ui_test_suite.py"
    if not launcher.is_file():
        raise ValueError("E_SUITE_MISSING: " + str(root))
    selected = runpy.run_path(str(launcher))["activate"]()
    from ui_test_core.suite import selected_suite
    owner = selected_suite(selected).load_package("artifact-governance")
    return import_module(owner.__name__ + ".commands").main()


if __name__ == "__main__":
    raise SystemExit(main())
