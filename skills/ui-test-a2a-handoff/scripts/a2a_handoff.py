"""Compatibility entry for the original local handoff command and Python API."""
import os
from pathlib import Path
import runpy
import sys


def _launcher():
    configured = os.environ.get("UI_TEST_SUITE")
    root = Path(configured.split(os.pathsep)[0]) if configured else Path(__file__).resolve().parents[2] / "ui-test"
    entry = root / "scripts/ui_test_suite.py"
    if not entry.is_file():
        raise ValueError(f"E_SUITE_MISSING: {root}")
    return runpy.run_path(str(entry))


def _owner():
    root = _launcher()["activate"]()
    from ui_test_core.suite import selected_suite
    return selected_suite(root).load_package("a2a-handoff")


def pack(source, review_notes=None):
    return _owner().pack(source, review_notes)


def load_json(path):
    return _owner().load_json(path)


def save_json(path, payload):
    return _owner().save_json(path, payload)


def main():
    _launcher()["main"](["a2a-handoff", *sys.argv[1:]], quiet=True)


if __name__ == "__main__":
    main()
