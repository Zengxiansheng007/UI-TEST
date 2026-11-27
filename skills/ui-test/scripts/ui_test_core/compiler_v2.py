"""Compatibility import for the selected script-build implementation."""
from importlib import import_module

from .suite import selected_suite

package = selected_suite().load_package("script-build")
implementation = import_module(package.__name__ + ".compiler_v2")
CompileV2Error = implementation.CompileV2Error
compile_case_v2 = implementation.compile_case_v2
