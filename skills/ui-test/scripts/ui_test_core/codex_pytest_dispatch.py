"""Load the selected playwright-run implementation for existing projects."""
from .suite import owner_module

owner_module("playwright-run", "codex_pytest_dispatch", __name__)
