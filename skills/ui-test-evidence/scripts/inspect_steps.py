"""Compatibility entry for the original UI-Test evidence skill."""
from importlib import import_module

from ui_test_core.suite import selected_suite

if __name__ == "__main__":
    owner = selected_suite().load_package("evidence")
    import_module(".inspect_steps", owner.__name__).main()
