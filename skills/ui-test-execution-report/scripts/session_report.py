"""Compatibility entry for the selected report implementation."""
from importlib import import_module
from report_compat import owner

_impl = import_module(".session_report", owner().__name__)
globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
