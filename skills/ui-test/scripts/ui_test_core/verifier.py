"""Compatibility import for the selected verify implementation."""
from importlib import import_module

from .suite import selected_suite

package = selected_suite().load_package("verify")
implementation = import_module(package.__name__ + ".verifier")
verify_postcondition = implementation.verify_postcondition
reconcile_midscene = implementation.reconcile_midscene
