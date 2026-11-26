"""Compatibility import for the selected script-build implementation."""
from importlib import import_module

from .suite import selected_suite

package = selected_suite().load_package("script-build")
implementation = import_module(package.__name__ + ".compiler")
CompileError = implementation.CompileError
build_dependency_graph = implementation.build_dependency_graph
affected_cases = implementation.affected_cases
compile_case = implementation.compile_case
create_compile_plan = implementation.create_compile_plan
sync_release = implementation.sync_release
validate_release = implementation.validate_release
retention_metadata = implementation.retention_metadata
ASSET_TYPES = implementation.ASSET_TYPES
STATUS_VALUES = implementation.STATUS_VALUES
