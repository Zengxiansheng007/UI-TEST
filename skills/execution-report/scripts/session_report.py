"""Read-only review of a controller's session and the caller's observed exit."""

import hashlib
import html
import json
from pathlib import Path

from ui_test_core.case_contracts import canonical_hash, validate_document
from ui_test_core.path_utils import io_path
from ui_test_core.session_evidence import verify_node_evidence
from ui_test_core.strict_json import StrictJsonError, load_strict_json


def reconcile(summary, document, evidence_root):
    """Keep recorded dispositions alongside the verification of each on-disk record."""
    issues = summary["issues"]
    if validate_document(document, "pytest-session-result-v2.schema.json"):
        issues.append("session-schema-invalid")
    if document.get("session_result_hash") != canonical_hash({k: v for k, v in document.items() if k != "session_result_hash"}):
        issues.append("session-hash-mismatch")
    if document.get("session_id") != summary["session_id"]:
        issues.append("session-id-mismatch")
    for field in ("session_result_hash", "batch_id", "expected_nodes", "worker_errors", "collection_consistent",
                  "pytest_exitstatus", "session_status", "all_required_nodes_committed"):
        summary[field] = document.get(field)
    denied = document.get("denied_duplicate_nodes", [])  # 历史 V2 记录可省略此字段。
    if isinstance(denied, list):
        summary["denied_duplicate_nodes"] = [node for node in denied if isinstance(node, str)]
    if summary["denied_duplicate_nodes"] and summary["session_status"] == "passed":
        issues.append("duplicate-dispatch-in-passed-session")
    if summary["expected_batch_id"] is not None and summary["expected_batch_id"] != summary["batch_id"]:
        issues.append("batch-id-mismatch")
    if summary["observed_exit_code"] is None:
        issues.append("observed-exit-missing")
    elif summary["observed_exit_code"] != summary["pytest_exitstatus"]:
        issues.append("exit-code-mismatch")
    if summary["worker_errors"] is None:
        issues.append("worker-errors-unreported")
    elif summary["worker_errors"] != []:
        issues.append("worker-error")
    if summary["collection_consistent"] is not True:
        issues.append("collection-unconfirmed")
    unexpected = document.get("unexpected_nodes", [])
    if isinstance(unexpected, list):
        summary["unexpected_nodes"] = [node for node in unexpected if isinstance(node, str)]
    if summary["unexpected_nodes"]:
        issues.append("unexpected-nodes")

    rows, expected = document.get("nodes"), document.get("expected_nodes")
    if not (isinstance(rows, list) and isinstance(expected, list) and all(isinstance(n, str) for n in expected)):
        return
    seen, runs = set(), set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("node_id"), str):
            continue  # The schema diagnostic already identifies malformed input.
        node_id, run_id = row["node_id"], row.get("run_id")
        if node_id in seen:
            issues.append("duplicate-node")
        seen.add(node_id)
        if isinstance(run_id, str):
            if run_id in runs:
                issues.append("duplicate-run-id")
            runs.add(run_id)
        valid = verify_node_evidence(evidence_root, summary["session_id"], row)
        summary["nodes"].append({**row, "evidence_verified": valid})
        if not valid:
            issues.append("node-evidence-invalid")
    summary["missing_nodes"] = [node for node in expected if node not in seen]
    if seen != set(expected):
        issues.append("node-set-mismatch")
    if issues:
        summary["issues"] = list(dict.fromkeys(issues))
        return
    all_passed = bool(expected) and all(row["disposition"] == "passed" for row in rows)
    if summary["session_status"] == "passed" and all_passed and summary["all_required_nodes_committed"] is True and summary["observed_exit_code"] == 0:
        summary["status"] = "passed"
    elif summary["session_status"] == "failed" and summary["observed_exit_code"] != 0:
        summary["status"] = "failed"
    else:
        issues.append("session-outcome-inconsistent")


def render_summary(summary, payload):
    def cell(value):
        return html.escape("" if value is None else str(value))

    rows = "".join("<tr>" + "".join(f"<td>{cell(node.get(key))}</td>" for key in
                   ("node_id", "run_id", "disposition", "terminal_ref", "evidence_verified", "missing_reason")) + "</tr>"
                   for node in summary["nodes"])
    denied = summary["denied_duplicate_nodes"]
    duplicate_section = ""
    if denied:
        nodes = "".join(f"<li>{cell(node)}</li>" for node in denied)
        duplicate_section = f"<h2>重复投递已拒绝</h2><p>以下节点已有执行尝试，本次投递未再次执行。</p><ul>{nodes}</ul>"
    extra_section = ""
    if summary["unexpected_nodes"]:
        nodes = "".join(f"<li>{cell(node)}</li>" for node in summary["unexpected_nodes"])
        extra_section = f"<h2>预期范围外的节点</h2><ul>{nodes}</ul>"
    return (f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>pytest 会话报告</title>'
            f'<h1>pytest 会话报告</h1><p>会话 {cell(summary["session_id"])} ｜ 批次 {cell(summary["batch_id"])}'
            f' ｜ 结论 <strong>{cell(summary["status"])}</strong></p>'
            f'<p>pytest 记录退出码 {cell(summary["pytest_exitstatus"])} ｜ 调用方观察退出码 {cell(summary["observed_exit_code"])}</p>'
            '<table><thead><tr><th>节点</th><th>运行编号</th><th>原处置</th><th>终态引用</th><th>凭据有效</th><th>缺失原因</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>{duplicate_section}{extra_section}'
            f'<h2>会话核对明细</h2><pre>{html.escape(payload)}</pre></html>')


def generate_session_report(source: Path, evidence_root: Path, output: Path, observed_exit, expected_batch,
                            scan_sensitive, *, stage_delivery=False):
    summary = {"session_id": source.stem, "status": "incomplete", "observed_exit_code": observed_exit,
               "pytest_exitstatus": None, "expected_batch_id": expected_batch, "batch_id": None,
               "external_acceptance": "not_provided", "nodes": [], "missing_nodes": [], "unexpected_nodes": [],
               "denied_duplicate_nodes": [], "issues": []}
    if source.resolve() != (evidence_root.resolve() / "sessions" / source.name) or source.suffix != ".json":
        summary["issues"].append("session-path-mismatch")
    elif not io_path(source).is_file():
        summary["issues"].append("session-result-missing")
    else:
        try:
            document = load_strict_json(io_path(source))
        except StrictJsonError:
            summary["issues"].append("session-result-unreadable")
        else:
            if not isinstance(document, dict) or document.get("schema_version") != "ui-test.pytest-session-result.v2":
                summary["issues"].append("expected-session-result-v2")
            elif scan_sensitive(document):
                raise ValueError("sensitive fields in session evidence")
            else:
                reconcile(summary, document, evidence_root)
    key = hashlib.sha256(str(source.resolve()).encode("utf8")).hexdigest()[:20]
    stage_ready = stage_delivery and not summary["issues"]
    directory = io_path(output / ("stage-reports" if stage_ready else "sessions") / key)
    if scan_sensitive(summary):
        raise ValueError("sensitive fields in session evidence")
    payload = json.dumps(summary, indent=2, ensure_ascii=False)
    if stage_ready:
        from ui_test_core.stage_delivery import formal_cases
        from .stage_report import render_stage_html

        cases = formal_cases(source, session_hash=summary["session_result_hash"], batch_id=expected_batch)
        if scan_sensitive(cases):
            raise ValueError("E_STAGE_SENSITIVE_FIELDS")
        document = render_stage_html("playwright", source.stem, cases)
        review = render_summary(summary, payload).split("<h1>", 1)[1].removesuffix("</html>")
        document = document.replace("</main>", '<details><summary>pytest 会话核对</summary><h1>' + review + "</details></main>", 1)
    else:
        document = render_summary(summary, payload)
    directory.mkdir(parents=True, exist_ok=True)
    summary_path = directory / "session-summary.json"
    report_path = directory / "report.html"
    from .stage_report import atomic_text
    atomic_text(summary_path, payload)
    atomic_text(report_path, document)
    return {"status": summary["status"], "artifact_kind": "stage-report" if stage_ready else "session-diagnostic",
            "execution_summary": str(summary_path), "report_html": str(report_path)}
