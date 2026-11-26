"""Project redacted step evidence from original Midscene or Playwright records."""
import base64
import hashlib
from pathlib import Path
import re

from ui_test_core.case_contracts import canonical_hash, validate_document
from ui_test_core.strict_json import loads_strict


VERSION = "ui-test.step-evidence.v1"
IDENTITY = ("run_id", "case_id", "branch_id", "attempt_ref", "step_id")
DIAGNOSTICS = {"locator_drift", "stale_source", "data_stale", "browser_disconnected",
               "environment_unavailable", "business_assertion_mismatch", "contract_mismatch",
               "permission_denied", "timeout"}
SENSITIVE = re.compile(r"password|secret|token|cookie|authorization|api[_-]?key|bearer", re.I)


def safe_identity(value):
    if (not isinstance(value, str) or not re.fullmatch(r"[\w./:-]{1,180}", value)
            or SENSITIVE.search(value) or ".." in value or value.startswith("/")):
        raise ValueError("E_STEP_IDENTITY")
    return value


def network_summary(fact, owner, session):
    """Only matched, current-session observations qualify as network evidence."""
    if not isinstance(fact, dict) or not session or not (
            fact.get("source") == "page-response" and fact.get("session_id") == session
            and fact.get("run_id") == owner["run_id"] and fact.get("request_matched") is True
            and fact.get("response_matched") is True and type(fact.get("status")) is int
            and 100 <= fact["status"] <= 599
            and all(fact.get(k, v) == v for k, v in owner.items())):
        return None
    return {"source": "page-response", "status": fact["status"],
            "evidence_ref": safe_identity(fact.get("evidence_ref"))}


def pictures(step, owner, root):
    items = list(step.get("images") or ([step["ui_evidence"]] if step.get("ui_evidence") else []))
    seen = {img.get("path") for img in items}
    for ref in step.get("evidence_refs", []):
        if ref not in seen and Path(ref).suffix.lower() in {".png", ".gif", ".jpg", ".jpeg", ".webp", ".bmp"}:
            items.append({"path": ref, "sha256": step.get("screenshot_sha256") if ref == step.get("screenshot_ref") else None})
    rows = []
    for img in items:
        if not isinstance(img, dict) or any(img.get(k, v) != v for k, v in owner.items()):
            raise ValueError("E_IMAGE_OWNER")
        ref = img.get("path")
        if img.get("data_uri"):
            header, marker, payload = img["data_uri"].partition(",")
            if ref or not marker or header not in {"data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"}:
                raise ValueError("E_IMAGE_SOURCE")
            digest = hashlib.sha256(base64.b64decode(payload, validate=True)).hexdigest()
            if img.get("sha256") and digest != img["sha256"].removeprefix("sha256:"):
                raise ValueError("E_IMAGE_DIGEST")
            rows.append({"inline_in_original": True, "sha256": digest})
            continue
        if not ref:
            # Preserve the original reason by pointer; private text stays in its original file.
            rows.append({"missing_reason": "see-original" if img.get("missing_reason") else "not-produced"})
            continue
        if not isinstance(ref, str) or ref.startswith(("//", "\\")) or ".." in Path(ref).parts:
            raise ValueError("E_IMAGE_SCOPE")
        candidate = root / ref
        if candidate.drive.casefold() != root.drive.casefold() or not candidate.is_relative_to(root):
            raise ValueError("E_IMAGE_SCOPE")
        path = candidate.resolve()
        if not path.is_relative_to(root):
            raise ValueError("E_IMAGE_SCOPE")
        relative = path.relative_to(root).as_posix()
        if SENSITIVE.search(relative) or re.search(r"[?#=]", relative):
            raise ValueError("E_IMAGE_PRIVATE_PATH")
        row = {"path": relative}
        if not path.is_file():
            row["missing_reason"] = "file-missing"
        else:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if img.get("sha256") and img["sha256"].removeprefix("sha256:") != digest:
                raise ValueError("E_IMAGE_DIGEST")
            row["sha256"] = digest
        rows.append(row)
    return rows


def source_cases(doc):
    if doc.get("schema_version") == "ui-test.run-result.v5":
        if (validate_document(doc, "run-result-v5.schema.json")
                or doc["run_result_hash"] != canonical_hash({k: v for k, v in doc.items() if k != "run_result_hash"})):
            raise ValueError("E_RUN_RESULT_INVALID")
        yield doc, doc["step_results"], "/step_results"
    elif doc.get("stage") == "midscene" and doc.get("cases"):
        for i, case in enumerate(doc["cases"]):
            if case.get("run_id") != doc.get("run_id"):
                raise ValueError("E_STEP_IDENTITY")
            yield case, case.get("steps"), f"/cases/{i}/steps"
    else:
        raise ValueError("E_STEP_SOURCE_REQUIRED")


def build_index(source, *, run_root=None):
    source = Path(source).resolve()
    root = Path(run_root or source.parent).resolve()
    raw = source.read_bytes()
    doc = loads_strict(raw.decode("utf-8"))
    rows, seen = [], set()
    for case, steps, prefix in source_cases(doc):
        if not isinstance(steps, list) or not steps:
            raise ValueError("E_STEP_MATERIAL_REQUIRED")
        for i, step in enumerate(steps):
            owner = {k: safe_identity(case.get(k)) for k in ("run_id", "case_id", "attempt_ref")}
            owner.update(branch_id=safe_identity(case.get("branch_id", owner["case_id"])),
                         step_id=safe_identity(step.get("step_id")))
            key = tuple(owner[k] for k in IDENTITY)
            if key in seen or any(step.get(k, v) != v for k, v in owner.items()):
                raise ValueError("E_STEP_IDENTITY")
            seen.add(key)
            capture_owner = {**owner, "stage": doc.get("stage", "playwright")}
            for field in ("session_id", "node_id"):
                if field in case or field in doc:
                    capture_owner[field] = case.get(field, doc.get(field))
            images = pictures(step, capture_owner, root)
            if images and step.get("status") in {"not_executed", "not-executed"}:
                raise ValueError("E_UNEXECUTED_IMAGE")
            network = network_summary(step.get("network_evidence"), owner, case.get("session_id", doc.get("session_id")))
            reason = step.get("reason")
            # Existing checkpoint observations can carry a separately evidenced diagnosis.
            attribution = step.get("failure_attribution")
            if isinstance(attribution, dict) and attribution.get("evidence_refs"):
                refs = step.get("evidence_refs", [])
                if all(ref in refs for ref in attribution["evidence_refs"]):
                    reason = attribution.get("failure_type")
            status = step.get("status")
            rows.append({**owner, "pointer": f"{prefix}/{i}", "screenshots": images,
                         "screenshot_missing": None if images else "not-produced",
                         "network": network, "network_missing": None if network else "no-matched-page-response",
                         "status": status if status in {"passed", "failed", "blocked", "degraded", "observed",
                                                        "not-executed", "not_executed", "timeout"} else "unknown",
                         "diagnostic": reason if isinstance(reason, str) and reason in DIAGNOSTICS else None})
    return {"schema_version": VERSION, "source_name": safe_identity(source.name), "source_sha256": hashlib.sha256(raw).hexdigest(), "steps": rows}
