"""Start the selected suite's dispatcher from the formal execution capability."""
from importlib import import_module
import os
import runpy
from pathlib import Path
import sys


def main():
    owner = Path(__file__).resolve().parents[1]
    choices = os.environ.get("UI_TEST_SUITE", "").split(os.pathsep)
    roots = {Path(value).resolve() for value in choices if value}
    if not roots:
        raise ValueError("E_SUITE_REQUIRED: set UI_TEST_SUITE to the main Skill directory")
    if len(roots) != 1:
        raise ValueError("E_SUITE_AMBIGUOUS: select one UI_TEST_SUITE")
    root = roots.pop()
    bootstrap = runpy.run_path(str(root / "scripts/ui_test_suite.py"))
    bootstrap["activate"](root)
    from ui_test_core.suite import selected_suite
    suite = selected_suite(root)
    if suite.skill_path("playwright-run") != owner:
        raise ValueError("E_SUITE_CONFLICT: run the selected suite's playwright-run entry")
    os.environ["UI_TEST_REQUIRE_FORMAL_V5"] = "1"
    package = suite.load_package("playwright-run")
    import_module(package.__name__ + ".dispatcher").cli()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit(str(exc))
