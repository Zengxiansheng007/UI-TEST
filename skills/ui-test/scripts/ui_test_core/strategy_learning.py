"""Compatibility entry for the selected experience Skill."""
from .suite import owner_module

implementation = owner_module("experience", "strategy_learning", __name__)
if __name__ == "__main__":
    implementation.main()
