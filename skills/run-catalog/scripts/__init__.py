"""Public API for registering UI test stages and attempts."""
from .run_catalog import refresh_catalog, register_stage
from .stage_events import record_attempt, stage_started
