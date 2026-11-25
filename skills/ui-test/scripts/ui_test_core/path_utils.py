"""Display-path and Windows extended-length I/O path helpers."""

from __future__ import annotations

import os
import hashlib
import json
from pathlib import Path


def short_id(*identity):
    """Hash a tuple of logical identifiers without mixing component boundaries."""
    if not all(isinstance(part, str) and part.strip() for part in identity):
        raise ValueError("E_ARTIFACT_IDENTITY")
    encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def canonical_display_path(path: str | Path) -> Path:
    """Return a normal absolute path suitable for manifests and user output."""
    text = str(path)
    if os.name == "nt" and text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif os.name == "nt" and text.startswith("\\\\?\\"):
        text = text[4:]
    return Path(os.path.abspath(text))


def io_path(path: str | Path) -> Path:
    """Return an extended-length Windows path for all filesystem operations."""
    display = str(canonical_display_path(path))
    if os.name != "nt":
        return Path(display)
    if display.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + display[2:])
    return Path("\\\\?\\" + display)

