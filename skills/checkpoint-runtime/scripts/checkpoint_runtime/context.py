"""Recover the current module with the selected suite's shared readiness contract."""
from datetime import datetime, timezone

from ui_test_core.module_ready import ModuleReadyObserver, consume_ready_context, validate_module_ready_context


def capture_context(page, *, packet, session_id, config, enter):
    observer = ModuleReadyObserver(page, packet=packet, session_id=session_id, config=config)
    try:
        enter(page)
        return observer.capture()
    finally:
        observer.close()


def recover_current(page, *, packet, session_id, config):
    """Observe the supplied Page without navigating, interacting or querying an endpoint."""
    if page is None:
        raise ValueError("E_CURRENT_PAGE_REQUIRED")
    scope = packet.get("scope", {})
    if (scope.get("risk_level") not in {"r0-read-only", "r1-read-only-authenticated"}
            or scope.get("module_path", [])[-1:] != [config.get("module_id")]):
        raise ValueError("E_MODULE_READY_TARGET_MISMATCH")
    return capture_context(page, packet=packet, session_id=session_id, config=config, enter=lambda _: None)


def validate_context(context, *, page, packet, session_id, config):
    missing = None
    if page is None:
        missing = "current_page"
    elif not isinstance(context, dict):
        missing = "ready_context"
    elif context.get("session_id") != session_id:
        missing = "session_mismatch"
    else:
        try:
            if datetime.fromisoformat(context["expires_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
                missing = "context_expired"
        except (KeyError, TypeError, ValueError, AttributeError):
            missing = "context_expiry"
    if missing:
        return {"ok": False, "code": "E_MODULE_READY_CONTEXT_INVALID", "blocking": True, "missing": missing}
    return consume_ready_context(context, page=page, packet=packet, session_id=session_id, config=config)
