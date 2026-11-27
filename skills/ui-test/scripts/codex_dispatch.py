"""Historical CLI for the selected playwright-run dispatcher."""
from importlib import import_module
from ui_test_core.suite import selected_suite

owner = selected_suite().load_package("playwright-run")
dispatcher = import_module(owner.__name__ + ".dispatcher")

if __name__ == "__main__":
    dispatcher.cli()
