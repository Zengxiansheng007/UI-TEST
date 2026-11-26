"""Compatibility import for the selected run-catalog capability."""
from importlib import import_module
from .suite import selected_suite


def __getattr__(name):
    owner = selected_suite().load_package("run-catalog")
    return getattr(import_module(owner.__name__ + ".catalog_html"), name)
