"""Read sealed worker results and publish at the enclosing controller's boundary."""
import hashlib
import sys
from pathlib import Path

from .case_contracts import canonical_hash, validate_document
from .execution_attempt_store import ExecutionAttemptStore
from .finalization_transaction import FinalizationTransaction
from .path_utils import canonical_display_path, io_path
from .session_evidence import verify_node_evidence
from .strict_json import load_strict_json


def report_engine():
    package = Path(__file__).resolve().parents[3] / "ui-test-execution-report" / "scripts"
    if not (package / "stage_report.py").is_file():
        raise ValueError("E_STAGE_REPORT_PACKAGE_REQUIRED: ui-test-execution-report")
    if str(package) not in sys.path:
        sys.path.insert(0, str(package))
    import generate_report
    import stage_report
    return generate_report, stage_report


def formal_step(step, run_root, evidence_index=None):
    """Project only screenshot references explicitly bound to this sealed step."""
    from .run_evidence_linker import _validate_relative_ref

    projected = {k: step[k] for k in ("step_id", "action", "expected_result", "actual_result",
                                      "status", "reason", "key_reason", "evidence_refs") if k in step}
    images = []
    for image in step.get("images", []):
        if "data_uri" in image:
            raise ValueError("E_STAGE_IMAGE_REF")
        if image.get("missing_reason") and not image.get("path"):
            images.append(dict(image))
            continue
        ref = image.get("path")
        _validate_relative_ref(ref, field="image.path")
        if ref not in step.get("evidence_refs", []) or not image.get("sha256"):
            raise ValueError("E_STAGE_IMAGE_REF")
        root = Path(run_root).resolve()
        source = (root / ref).resolve()
        if not source.is_relative_to(root):
            raise ValueError("E_STAGE_IMAGE_REF")
        images.append({**image, "path": str(source), "source_ref": ref})
    bound = {image.get("source_ref") for image in images}
    for ref in step.get("evidence_refs", []):
        if ref in bound:
            continue
        _validate_relative_ref(ref, field="step.evidence_refs")
        if Path(ref).suffix.lower() not in {".png", ".gif", ".jpg", ".jpeg", ".webp", ".svg", ".bmp"}:
            continue
        source = (Path(run_root) / ref).resolve()
        if not source.is_relative_to(Path(run_root).resolve()):
            raise ValueError("E_STAGE_IMAGE_REF")
        image = dict(role="ordinary", source_ref=ref, caption=ref)
        if ref not in (evidence_index or {}).get("evidence_refs", []):
            image["missing_reason"] = "封存索引缺少此截图引用"
        elif step.get("screenshot_ref") == ref and step.get("screenshot_sha256"):
            image.update(path=str(source), sha256=step["screenshot_sha256"])
        else:
            image["missing_reason"] = "封存记录缺少原图字节摘要"
        images.append(image)
    if images:
        projected["images"] = images
    return projected


def formal_cases(source, *, session_hash=None, batch_id=None):
    source = canonical_display_path(source)
    root = source.parent.parent
    session = load_strict_json(io_path(source))
    if (source.parent.name != "sessions" or validate_document(session, "pytest-session-result-v2.schema.json")
            or session["session_id"] != source.stem
            or canonical_hash({k: v for k, v in session.items() if k != "session_result_hash"}) != session["session_result_hash"]
            or (session_hash is not None and session["session_result_hash"] != session_hash)
            or (batch_id is not None and session.get("batch_id") != batch_id)
            or session["expected_nodes"] != [n["node_id"] for n in session["nodes"]]):
        raise ValueError("E_STAGE_SESSION_IDENTITY")
    runs = [n["run_id"] for n in session["nodes"] if n.get("run_id")]
    if len(set(runs)) != len(runs) or len(set(session["expected_nodes"])) != len(session["expected_nodes"]):
        raise ValueError("E_STAGE_DUPLICATE_RUN_OR_NODE")
    legacy, _ = report_engine()
    cases = []
    for row in session["nodes"]:
        case = {**row, "session_id": source.stem, "status": row["disposition"], "steps": []}
        if row.get("missing_reason") in {"invalid-transaction", "invalid-terminal-or-receipt", "conflicting-deliveries", "phase-report-mismatch"}:
            raise ValueError("E_STAGE_NODE_EVIDENCE_CONFLICT")
        if row.get("terminal_ref") or row["finalization_status"] == "committed":
            if not verify_node_evidence(root, source.stem, row):
                raise ValueError("E_STAGE_NODE_EVIDENCE_CONFLICT")
        if row["finalization_status"] == "committed":
            store = ExecutionAttemptStore(evidence_root=root)
            run_root = store.session_run_target(run_id=row["run_id"], node_id=row["node_id"])
            closure = FinalizationTransaction(run_root).read_committed(immutable_snapshot=True)
            if not closure or canonical_hash(closure["receipt"]) != row["receipt_hash"]:
                raise ValueError("E_STAGE_RECEIPT_CONFLICT")
            result = closure["run_result"]
            report = {**row, "session_id": source.stem, "case_id": result["case_id"],
                      "transaction_id": closure["manifest"]["transaction_id"]}
            legacy.build_canonical_run_result(dict(run_result=result, report=report), Path(run_root))
            steps = [formal_step(step, run_root, closure["evidence_index"]) for step in result["step_results"]]
            case.update(case_id=result["case_id"], status=result["overall_status"], steps=steps,
                        run_result_hash=result["run_result_hash"], evidence_index=closure["evidence_index"],
                        run_result=result, run_root=str(run_root))
        else:
            case["reason"] = row.get("missing_reason") or row["finalization_status"]
        cases.append(case)
    return cases


def publish_session(source):
    source = canonical_display_path(source)
    cases = formal_cases(source)
    _, engine = report_engine()
    return engine.publish_stage_report("playwright", source.stem, cases, source.parent.parent / "stage-reports" / source.stem)


def publish_batch(task, batch_id, batch):
    rows = batch["runs"]
    references = dict.fromkeys((row["session_ref"], row["session_hash"]) for row in rows)
    archive = {}
    runs = set()
    for source, digest in references:
        for case in formal_cases(source, session_hash=digest, batch_id=batch_id):
            run_id = case.get("run_id")
            if run_id is not None and run_id in runs:
                raise ValueError("E_STAGE_DUPLICATE_RUN")
            runs.add(run_id)
            archive[source, digest, case["node_id"]] = case
    cases = []
    for row in rows:
        key = (row["session_ref"], row["session_hash"], row["node_id"])
        case = archive.pop(key, None)  # A second delivery of the same session row is not another attempt.
        if case is None:
            raise ValueError("E_STAGE_BATCH_IDENTITY")
        reserved_only = (case["status"] == "not_executed" and not case.get("attempt_ref")
                         and not case.get("run_id") and row.get("disposition") == "not_executed")
        if not reserved_only and case.get("run_id") != row["run_id"]:
            raise ValueError("E_STAGE_BATCH_IDENTITY")
        cases.append(case)
    if archive or set(batch["nodes"]) != {case["node_id"] for case in cases}:
        raise ValueError("E_STAGE_BATCH_IDENTITY")
    _, engine = report_engine()
    key = hashlib.sha256(batch_id.encode()).hexdigest()[:24]
    output = task.parent / (task.name + ".reports") / key
    return engine.publish_stage_report("playwright", batch_id, cases, output)
