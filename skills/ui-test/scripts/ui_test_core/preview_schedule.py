"""Compatibility import for the selected artifact-governance capability."""
from .suite import owner_module

implementation = owner_module("artifact-governance", "preview_schedule", __name__)
