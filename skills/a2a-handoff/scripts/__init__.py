from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


SENSITIVE_MARKERS = (
    "sk-",
    "bearer ",
    "token",
    "cookie",
    "password",
    "passwd",
    "secret",
    "Authorization:",
    "authorization",
)


def _canonical(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canonical(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_canonical(i) for i in obj]
    return obj


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(_canonical(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _reject_sensitive_refs(refs: List[Any]) -> None:
    for item in refs:
        text = json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
        lowered = text.lower()
        for marker in SENSITIVE_MARKERS:
            if marker.lower() in lowered:
                raise ValueError(f"sensitive marker found in artifact_refs: {marker}")
        if len(text) > 1200:
            raise ValueError("artifact_refs item is too long; keep only stable references")


def pack(source: Dict[str, Any], review_notes: Dict[str, Any] | None = None) -> Dict[str, Any]:
    from ui_test_core.packet_validator import validate_packet
    errors = validate_packet(source)
    if errors:
        raise ValueError("; ".join(f"{error['code']} at {error['path']}" for error in errors))
    _reject_sensitive_refs(source["artifact_refs"])
    notes = review_notes if review_notes is not None else {}
    if not isinstance(notes, dict) or set(notes) - {"revision_notes"}:
        raise ValueError("review notes may only supply revision_notes")
    revision_notes = notes.get("revision_notes", [])
    if not isinstance(revision_notes, list) or not all(isinstance(item, str) for item in revision_notes):
        raise ValueError("revision_notes must be a string array")
    common = deepcopy(source)
    common["source_packet_id"] = source["packet_id"]
    handoff = dict(deepcopy(common), handoff_id=_stable_id("handoff", source))
    prompt = dict(deepcopy(common), prompt_id=_stable_id("prompt", {"source": source, "notes": notes}),
                  revision_notes=deepcopy(revision_notes))
    return {"handoff_packet": handoff, "prompt_packet": prompt,
            "artifact_refs": {"source_packet_id": source["packet_id"], "refs": deepcopy(source["artifact_refs"])},
            "summary": {"source_packet_id": source["packet_id"], "handoff_id": handoff["handoff_id"],
                        "prompt_id": prompt["prompt_id"], "next_action": source["next_action"]}}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def deliver(args):
    source = load_json(args.source)
    review_notes = load_json(args.review_notes) if args.review_notes else None
    bundle = pack(source, review_notes)
    target = args.output
    if args.project:
        if not args.stage or not args.stage_run_id:
            raise ValueError("--project requires --stage and --stage-run-id")
        from ui_test_core.artifact_layout import ProjectLayout
        layout = ProjectLayout(args.project)
        target = layout.related_file(layout.run_dir(args.stage, args.stage_run_id), "交接", bundle["summary"]["prompt_id"])
        target.parent.mkdir(parents=True, exist_ok=True)
        from ui_test_core.codex_dispatch_state import publish
        publish(target, bundle)
    else:
        save_json(target, bundle)
    return {"output": str(target), "source_packet_id": source["packet_id"]}
