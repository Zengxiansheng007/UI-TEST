#!/usr/bin/env python3
"""Validate ui-test-execution-report skill and generated artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


SECRET_RE = re.compile(
    r"(password\s*[:=]\s*['\"][^'\"]+|authorization\s*[:=]\s*['\"][^'\"]+|cookie\s*[:=]\s*['\"][^'\"]+|sk-[A-Za-z0-9_-]{20,})",
    re.IGNORECASE,
)


def finding(severity: str, rule: str, message: str, path: Path | None = None) -> dict[str, str]:
    item = {"severity": severity, "rule": rule, "message": message}
    if path:
        item["path"] = str(path)
    return item


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_skill(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    from report_compat import runtime
    assets = runtime().skill_path("execution-report") / "assets"
    required = [
        root / "SKILL.md",
        root / "agents" / "openai.yaml",
        root / "references" / "report-contract.md",
        root / "scripts" / "generate_report.py",
        root / "scripts" / "image_viewer.py",
        assets / "image-viewer.css",
        assets / "image-viewer.js",
        root / "assets" / "sample-run.json",
        root / "docs" / "requirement-anchor.json",
        root / "docs" / "development-plan.md",
        root / "docs" / "test-plan.md",
    ]
    for path in required:
        if not path.exists():
            findings.append(finding("P0", "missing-required-file", f"missing {path.name}", path))
    skill = root / "SKILL.md"
    if skill.exists():
        text = read_text(skill)
        if "name: ui-test-execution-report" not in text:
            findings.append(finding("P0", "frontmatter-name", "SKILL.md name must match folder", skill))
        for ref in ("references/report-contract.md", "scripts/generate_report.py", "scripts/validate_execution_report_skill.py"):
            if ref not in text:
                findings.append(finding("P1", "missing-skill-reference", f"SKILL.md must reference {ref}", skill))
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".py", ".yaml", ".html"}:
            text = read_text(path)
            if SECRET_RE.search(text):
                findings.append(finding("P0", "secret-pattern", "possible live secret found", path))
    return findings


def find_report(root: Path) -> Path | None:
    matches = list((root / "human-html").rglob("report.html"))
    return matches[0] if matches else None


def validate_generated(root: Path) -> list[dict[str, str]]:
    stage = root / "stage-reports"
    if stage.is_dir():
        findings = validate_generated_layout(stage)
        if (root / "human-html").is_dir() or (root / "agent-readable").is_dir():
            findings.extend(validate_generated_layout(root))
        return findings
    return validate_generated_layout(root)


def validate_generated_layout(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    report = find_report(root)
    if not report:
        return [finding("P0", "generated-report-missing", "report.html not found", root)]
    text = read_text(report)
    # 样例校验仅统计证据单元格；缺图占位不代表真实截图已交付。
    screenshot_cell_count = text.count("截图缩略图（点击放大）") + text.count('data-ui-image-missing=')
    api_count = text.count("点击查看 JSON")
    stage = 'aria-label="用例与关键节点"' in text
    markers = ("Playwright 正式执行报告", "证据索引与运行来源") if stage else ("附件索引（治理用）", "接口汇总索引（治理用）", "第 4 章")
    for marker in markers:
        if marker not in text:
            findings.append(finding("P1", "generated-marker-missing", f"missing marker {marker}", report))
    for legacy in ("完整截图墙", "旧版独立证据展示区", "证据与 JSON</th>"):
        if legacy in text:
            findings.append(finding("P1", "legacy-evidence-wall", f"legacy evidence wall marker remains: {legacy}", report))
    if SECRET_RE.search(text):
        findings.append(finding("P0", "generated-secret-pattern", "generated HTML contains possible live secret", report))
    evidence = list((root / "agent-readable").rglob("evidence-index.json"))
    summary = list((root / "agent-readable").rglob("execution-summary.json"))
    run_results = list((root / "agent-readable").rglob("run-result.json"))
    if not evidence:
        findings.append(finding("P0", "evidence-index-missing", "evidence-index.json not found", root))
    else:
        data = json.loads(read_text(evidence[0]))
        if data.get("layout_contract") != ("stage-report" if stage else "step-table-embedded-evidence"):
            findings.append(finding("P1", "layout-contract-missing", "layout_contract must be step-table-embedded-evidence", evidence[0]))
    if not summary:
        findings.append(finding("P0", "execution-summary-missing", "execution-summary.json not found", root))
    else:
        data = json.loads(read_text(summary[0]))
        if (data.get("ui_screenshot_count") != (text.count('class="ui-image-trigger"') if stage else screenshot_cell_count)
                or (not stage and data.get("api_assertion_count") != api_count)):
            findings.append(finding("P1", "summary-counts-invalid", "HTML evidence counts differ from summary", summary[0]))
    if not run_results:
        findings.append(finding("P0", "canonical-run-result-missing", "run-result.json not found", root))
    else:
        canonical = json.loads(read_text(run_results[0]))
        from report_compat import runtime
        runtime()
        from ui_test_core.run_evidence_linker import canonical_hash, validate_document
        digest = canonical_hash({k: v for k, v in canonical.items() if k != "run_result_hash"})
        if validate_document(canonical, "run-result-v5.schema.json") or digest != canonical.get("run_result_hash"):
            findings.append(finding("P0", "invalid-v5", "V5 schema or canonical hash mismatch", run_results[0]))
        if canonical.get("schema_version") != "ui-test.run-result.v5":
            findings.append(finding("P0", "canonical-run-result-invalid", "run-result.json is not the canonical RunResult schema", run_results[0]))
        if summary and json.loads(read_text(summary[0])).get("status") != canonical.get("overall_status"):
            findings.append(finding("P0", "result-source-conflict", "execution-summary status differs from canonical RunResult", summary[0]))
        if summary and json.loads(read_text(summary[0])).get("source_run_result_hash") != canonical.get("run_result_hash"):
            findings.append(finding("P0", "result-hash-conflict", "execution-summary hash differs from canonical RunResult", summary[0]))
    return findings


class EmbeddedResourceParser(HTMLParser):
    """资源地址与溯源文字分离；拒绝单文件之外的渲染依赖。"""
    def __init__(self):
        super().__init__()
        self.external = []
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "style":
            self.in_style = True
        if tag == "img":
            source = values.get("src", "")
            if not re.fullmatch(r"data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+", source):
                self.external.append("img.src must embed bitmap bytes")
        for attr in ("src", "srcset", "poster", "data"):
            if attr in values and tag in {"img", "script", "source", "video", "audio", "iframe", "object", "embed", "input"}:
                if tag != "img" or attr != "src":
                    self.external.append(f"external resource attribute: {tag}.{attr}")
        if tag == "link" and values.get("href"):
            self.external.append("linked resource")
        if "style" in values:
            self.check_css(values["style"])

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.check_css(data)

    def check_css(self, css):
        if re.search(r"@import\b|url\s*\(", css, re.I):
            self.external.append("CSS resource reference is not allowed in standalone report")


def validate_image_viewer(report: Path) -> list[dict[str, str]]:
    """校验图片查看器的离线集成，不替代报告结果契约。"""
    text = read_text(report)
    items = []
    for marker in ('id="ui-image-viewer-style"', 'id="ui-image-viewer-script"',
                   'ui-image-trigger', 'showModal()', 'data-viewer-action="actual"',
                   'data-viewer-action="fit-width"', 'data-viewer-action="close"'):
        if marker not in text:
            items.append(finding("P1", "image-viewer-contract", f"missing viewer marker: {marker}", report))
    resources = EmbeddedResourceParser()
    resources.feed(text)
    for issue in sorted(set(resources.external)):
        items.append(finding("P1", "image-viewer-offline", issue, report))
    return items


def summarize(findings: list[dict[str, str]]) -> dict[str, Any]:
    summary = {"P0": 0, "P1": 0, "P2": 0}
    for item in findings:
        if item["severity"] in summary:
            summary[item["severity"]] += 1
    return {
        "status": "passed" if summary["P0"] == 0 and summary["P1"] == 0 else "failed",
        "summary": summary,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_folder", type=Path)
    parser.add_argument("--generated-root", type=Path)
    parser.add_argument("--html-report", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    findings = validate_skill(args.skill_folder)
    if args.generated_root:
        findings.extend(validate_generated(args.generated_root))
    if args.html_report:
        findings.extend(validate_image_viewer(args.html_report))
    report = summarize(findings)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output, encoding="utf-8")
    print(output)
    return 1 if report["summary"]["P0"] or report["summary"]["P1"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
