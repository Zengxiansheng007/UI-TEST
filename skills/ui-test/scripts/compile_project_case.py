"""Compile a project case with the selected script-build implementation."""
from importlib import import_module

from ui_test_core.suite import selected_suite


def main():
    package = selected_suite().load_package("script-build")
    return import_module(package.__name__ + ".compile_project_case").main()


if __name__ == "__main__":
    raise SystemExit(main())
