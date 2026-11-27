"""Compatibility API for the selected repair owner."""
from .suite import owner_module

implementation = owner_module("repair", "asset_repair", __name__)
