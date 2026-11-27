"""Load the selected playwright-run implementation for existing projects."""
from .suite import owner_module

owner_module("playwright-run", "pytest_runtime_plugin", __name__)
