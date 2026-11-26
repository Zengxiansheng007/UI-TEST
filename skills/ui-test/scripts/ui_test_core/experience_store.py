"""Compatibility entry for the selected experience Skill."""
from .suite import owner_module

implementation = owner_module("experience", "experience_store", __name__)
