"""Checkpoint runtime uses the main skill's current-session readiness contract."""
from pathlib import Path
import sys

_core = Path(__file__).resolve().parents[3] / "ui-test" / "scripts"
if str(_core) not in sys.path:
    sys.path.insert(0, str(_core))

from ui_test_core.module_ready import ModuleReadyObserver, consume_ready_context, validate_module_ready_context


def capture_context(page, *, packet, session_id, config, enter):
    observer = ModuleReadyObserver(page, packet=packet, session_id=session_id, config=config)
    try:
        enter(page)
        return observer.capture()
    finally:
        observer.close()


def validate_context(context, *, page, packet, session_id, config):
    return consume_ready_context(context, page=page, packet=packet, session_id=session_id, config=config)
