"""Checkpoint identity, promotion, signature, staleness and read-only policy."""

from __future__ import annotations

import hashlib
import json
from .module_ready import build_module_ready_context, validate_module_ready_context, verify_module_signature
from collections import Counter
from dataclasses import dataclass

SCOPE_FIELDS = ("project_group", "product", "system", "module_path", "function", "checkpoint", "environment", "risk_level")


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checkpoint_identity(scope: dict, module_id: str, version: int = 1) -> dict:
    missing = [field for field in SCOPE_FIELDS if not scope.get(field)]
    if missing:
        raise ValueError(f"missing scope fields: {','.join(missing)}")
    if not isinstance(scope["module_path"], list) or not scope["module_path"]:
        raise ValueError("E_CHECKPOINT_MODULE_PATH_INVALID")
    if scope["risk_level"] not in {"r0-read-only", "r1-read-only-authenticated"}:
        raise ValueError("E_CHECKPOINT_RISK_UNSUPPORTED")
    logical = {field: scope[field] for field in SCOPE_FIELDS}
    logical["module_id"] = module_id
    digest = hashlib.sha256(_canonical(logical).encode("utf-8")).hexdigest()[:20]
    return {"module_id": module_id, "checkpoint_id": f"cp-{digest}", "checkpoint_version": version, "scope": logical}


def promotion_status(attempts: list[dict], user_activated: bool = False) -> str:
    deterministic_sessions = {item.get("session_id") for item in attempts if item.get("deterministic_pass") and not item.get("retry_of")}
    if user_activated and len(deterministic_sessions) >= 2:
        return "active"
    if len(deterministic_sessions) >= 2:
        return "eligible"
    if len(deterministic_sessions) == 1:
        return "validated"
    if attempts:
        return "candidate"
    return "blocked"


def stale_decision(*, signature_conflict: bool = False, version_conflict: bool = False, permission_conflict: bool = False, policy_conflict: bool = False, failed_attempts: list[dict] | None = None) -> dict:
    if signature_conflict or version_conflict or permission_conflict or policy_conflict:
        return {"status":"stale","reason":"immediate-conflict"}
    roots = Counter(item.get("root_cause") for item in (failed_attempts or []) if item.get("independent_session") and item.get("root_cause"))
    if any(count >= 2 for count in roots.values()):
        return {"status":"stale","reason":"same-root-two-independent-failures"}
    return {"status":"degraded" if roots else "active","reason":None}


def rebuild_scope(chain: list[str], failed_checkpoint_id: str) -> list[str]:
    if failed_checkpoint_id not in chain:
        raise ValueError("E_CHECKPOINT_UNKNOWN")
    return chain[chain.index(failed_checkpoint_id):]


@dataclass(frozen=True)
class SemanticReadonlySignature:
    method: str
    path_sha256: str
    content_type: str
    query_keys: tuple[str, ...]
    body_keys: tuple[str, ...]
    max_requests_per_session: int = 4

    def matches(self, request: dict, count: int) -> bool:
        normalized = normalize_semantic_readonly_request(request)
        return (
            count <= self.max_requests_per_session
            and normalized.get("method", "").upper() == self.method.upper()
            and normalized.get("path_sha256") == self.path_sha256
            and normalized.get("content_type", "").split(";", 1)[0].strip().lower() == self.content_type.lower()
            and tuple(sorted(normalized.get("query_keys", []))) == tuple(sorted(self.query_keys))
            and tuple(sorted(normalized.get("body_keys", []))) == tuple(sorted(self.body_keys))
            and not any(key in normalized for key in ("raw_url", "query_values", "payload_values", "body_values"))
        )


def normalize_semantic_readonly_request(request: dict) -> dict:
    normalized = dict(request)
    if "body_keys" not in normalized and "payload_keys" in normalized:
        normalized["body_keys"] = normalized["payload_keys"]
        normalized["legacy_payload_keys_accepted"] = True
    normalized["query_keys"] = sorted(set(normalized.get("query_keys", [])))
    normalized["body_keys"] = sorted(set(normalized.get("body_keys", [])))
    normalized.pop("payload_keys", None)
    return normalized
