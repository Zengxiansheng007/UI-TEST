"""Load the selected playwright-run implementation for existing projects."""
from .suite import owner_module

owner_module("playwright-run", "codex_dispatch_state", __name__)
