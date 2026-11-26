"""Read sealed worker results and publish at the enclosing controller's boundary."""
from pathlib import Path

from .case_contracts import canonical_hash, validate_document
from .artifact_layout import ProjectLayout, batch_stage_id, dispatch_task_ref
from .execution_attempt_store import ExecutionAttemptStore
from .finalization_transaction import FinalizationTransaction
from .path_utils import canonical_display_path, io_path
from .session_evidence import verify_node_evidence
from .strict_json import load_strict_json
from .stage_origin import recorded_origin


def report_engine():
    from .suite import selected_suite
    owner = selected_suite().load_package("execution-report")
    return owner.generate_report, owner.stage_report


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
        case = {**row, **session.get("selected_cases", {}).get(row["node_id"], {}), "execution_source": str(source), "evidence_source": None,
                "started_at": session.get("started_at"), "ended_at": session["recorded_at"],
                "session_status": session["session_status"], "session_id": source.stem, "status": row["disposition"], "steps": []}
        if row.get("missing_reason") in {"invalid-transaction", "invalid-terminal-or-receipt", "conflicting-deliveries", "phase-report-mismatch"}:
            raise ValueError("E_STAGE_NODE_EVIDENCE_CONFLICT")
        if row.get("terminal_ref") or row["finalization_status"] == "committed":
            if not verify_node_evidence(root, source.stem, row):
                raise ValueError("E_STAGE_NODE_EVIDENCE_CONFLICT")
            if row.get("terminal_ref"):
                case["evidence_source"] = str(root / row["terminal_ref"])
        if row.get("terminal_ref"):
            context = ExecutionAttemptStore(evidence_root=root).read_execution_context(run_id=row["run_id"], node_id=row["node_id"])
            if context and context.get("binding"):
                case.update(binding=context["binding"], version=context["binding"]["version"])
        if row["finalization_status"] == "committed":
            store = ExecutionAttemptStore(evidence_root=root)
            run_root = store.session_run_target(run_id=row["run_id"], node_id=row["node_id"])
            closure = FinalizationTransaction(run_root).read_committed(immutable_snapshot=True)
            if not closure or canonical_hash(closure["receipt"]) != row["receipt_hash"]:
                raise ValueError("E_STAGE_RECEIPT_CONFLICT")
            result = closure["run_result"]
            if case.get("binding") and canonical_hash(context) != result["execution_context_hash"]:
                raise ValueError("E_STAGE_VERSION_CONTEXT_CONFLICT")
            report = {**row, "session_id": source.stem, "case_id": result["case_id"],
                      "transaction_id": closure["manifest"]["transaction_id"]}
            legacy.build_canonical_run_result(dict(run_result=result, report=report), Path(run_root))
            steps = [formal_step(step, run_root, closure["evidence_index"]) for step in result["step_results"]]
            final_root = Path(run_root) / "finalization"
            case.update(branch_id=result["branch_id"],
                        execution_source=str(final_root / closure["manifest"]["run_result_ref"]),
                        evidence_source=str(final_root / closure["manifest"]["evidence_index_ref"]))
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
    project = ProjectLayout.from_evidence(source)
    output = project.reserve_run("playwright", source.stem) if project else source.parent.parent / "stage-reports" / source.stem
    delivery = engine.publish_stage_report("playwright", source.stem, cases, output,
                                           origin=recorded_origin(output, "playwright", source.stem))
    if project:
        from .catalog_delivery import catalog_delivery
        catalog_delivery(project.root, source.stem, "playwright", cases, delivery, started_at=cases[0]["started_at"],
                         ended_at=cases[0]["ended_at"], status=cases[0]["session_status"])
    return delivery


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
    projects = {project.root if (project := ProjectLayout.from_evidence(source)) else None for source, _ in references}
    project = ProjectLayout(projects.pop()) if len(projects) == 1 and None not in projects else ProjectLayout(task.parent)
    batch_id = batch_stage_id(dispatch_task_ref(task), batch_id)
    output = project.reserve_run("playwright", batch_id)
    delivery = engine.publish_stage_report("playwright", batch_id, cases, output,
                                           origin=recorded_origin(output, "playwright", batch_id))
    if all(case.get("execution_source") for case in cases):
        from .catalog_delivery import catalog_delivery
        catalog_delivery(project.root, batch_id, "playwright", cases, delivery, started_at=batch.get("started_at"),
                         ended_at=max(c["ended_at"] for c in cases), status=batch["status"])
    return delivery
