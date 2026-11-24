"""独立于表格宽度的真实截图查看器，支持离线报告。"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any

ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets"


def local_io_path(path: Path) -> Path:
    """Keep original publication URLs while allowing long Windows I/O paths."""
    value = str(path.absolute())
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def _mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def resolve_image_source(evidence: dict[str, Any]) -> tuple[str | None, str | None]:
    data_uri = evidence.get("data_uri")
    try:
        if data_uri:
            match = re.fullmatch(r"data:image/(?:png|jpeg|gif|webp);base64,([A-Za-z0-9+/=]+)", data_uri)
            if not match:
                return None, "unsupported-image-source"
            data = base64.b64decode(match.group(1), validate=True)
        else:
            value = evidence.get("path")
            if not value or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", str(value)):
                return None, "local-image-not-provided"
            data = local_io_path(Path(value)).read_bytes()
    except (OSError, ValueError):
        return None, "image-unavailable"
    expected = evidence.get("sha256")
    if expected and str(expected).removeprefix("sha256:").lower() != hashlib.sha256(data).hexdigest():
        raise ValueError("E_UI_IMAGE_HASH_MISMATCH")
    mime = _mime(data)
    if mime is None:
        return None, "unsupported-image-format"
    return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii"), None


def render_image_evidence(evidence: dict[str, Any], title: str = "UI截图", *, inline_metadata: bool = True,
                          resolved_source: tuple[str | None, str | None] | None = None) -> str:
    """缩略图只作入口；全尺寸原图在视口级dialog中显示。"""
    escape = lambda value: html.escape(str(value), quote=True)
    source, reason = resolved_source if resolved_source is not None else resolve_image_source(evidence)
    metadata = {key: value for key, value in evidence.items() if key != "data_uri"}
    details = escape(json.dumps(metadata, ensure_ascii=False, indent=2))
    if source is None:
        why = evidence.get("missing_reason") or reason
        return f'<div class="ui-image-missing" data-ui-image-missing="{escape(why)}">截图缺失：{escape(why)}<details><summary>证据引用</summary><pre>{details}</pre></details></div>'
    label = escape(title)
    meta_panel = f'<details class="ui-image-evidence-meta"><summary>证据元数据</summary><pre>{details}</pre></details>' if inline_metadata else ""
    metadata_attr = escape(json.dumps(metadata, ensure_ascii=False))
    return (
        f'<div class="ui-image-evidence"><button type="button" class="ui-image-trigger" '
        f'aria-label="放大截图：{label}" title="放大截图" data-image-title="{label}" '
        f'data-image-path="{escape(evidence.get("path", ""))}" data-image-metadata="{metadata_attr}">'
        f'<span>截图缩略图（点击放大）</span><img class="ui-image-thumb" src="{source}" alt="{label}" /></button>'
        f'{meta_panel}</div>'
    )


def install_image_viewer(document: str) -> str:
    """把固定查看器资源内嵌到单份HTML，重复调用保持幂等。"""
    if 'id="ui-image-viewer-script"' in document:
        return document
    if "</head>" not in document or "</body>" not in document:
        raise ValueError("E_UI_IMAGE_DOCUMENT_STRUCTURE")
    css = (ASSET_ROOT / "image-viewer.css").read_text(encoding="utf-8")
    script = (ASSET_ROOT / "image-viewer.js").read_text(encoding="utf-8")
    return document.replace("</head>", '<style id="ui-image-viewer-style">' + css + "</style></head>", 1).replace(
        "</body>", '<script id="ui-image-viewer-script">' + script + "</script></body>", 1
    )
