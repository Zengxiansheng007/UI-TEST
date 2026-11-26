"""Compatibility entry for the selected assets Skill."""
from .suite import owner_module

implementation = owner_module("assets", "asset_revision", __name__)
