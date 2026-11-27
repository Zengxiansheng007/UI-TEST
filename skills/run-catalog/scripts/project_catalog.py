"""Refresh the selected project's catalog or return a historical run as JSON."""
import argparse
from importlib import import_module
import json
from pathlib import Path

from ui_test_core.suite import selected_suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    for option in ("stage", "case", "branch", "attempt", "original"):
        parser.add_argument("--" + option)
    args = parser.parse_args()
    if not args.project.is_dir():
        parser.error("project directory is missing")
    owner = selected_suite().load_package("run-catalog")
    selectors = {key: value for key, value in vars(args).items() if key != "project" and value is not None}
    if selectors:
        result = import_module(owner.__name__ + ".lookup").lookup(args.project, **selectors)
        print(json.dumps(result, ensure_ascii=True))
    else:
        index = import_module(owner.__name__ + ".run_catalog").refresh_catalog(args.project)
        print(index)


if __name__ == "__main__":
    main()
