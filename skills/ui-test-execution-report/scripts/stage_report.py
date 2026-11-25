"""Publish one offline document from the cases already recorded for a stage."""
import html
import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from image_viewer import install_image_viewer, local_io_path, render_image_evidence, resolve_image_source


def atomic_text(path, value):
    path = local_io_path(path)
    with NamedTemporaryFile(dir=path.parent, prefix=".stage-", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(value, encoding="utf8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def escaped(value):
    return html.escape(str(value), quote=True)


STATE_LABELS = {"failed": "失败", "blocked": "阻塞", "skipped": "跳过", "unknown": "结果未知",
                "not_executed": "未执行", "not-executed": "未执行", "error": "错误"}


def status_label(status):
    return f"{status} · {STATE_LABELS[status]}" if status in STATE_LABELS else str(status)


def recorded_action(step):
    return step.get("recorded", True) and step.get("status") not in {"not-executed", "not_executed", "skipped"}


def check_image_identity(stage, case, step):
    """Optional legacy metadata must agree with the enclosing, stage-verified record."""
    owner = {field: case.get(field) for field in ("run_id", "case_id", "branch_id", "attempt_ref", "node_id", "session_id")}
    owner.update(stage=stage, step_id=step.get("step_id"))
    for image in step_images(step):
        if any(field in image and image[field] != expected for field, expected in owner.items()):
            raise ValueError("E_STAGE_IMAGE_IDENTITY")
        if step.get("status") in {"not_executed", "not-executed"}:
            raise ValueError("E_STAGE_UNEXECUTED_IMAGE")


def step_images(step):
    return step.get("images", []) or ([step["ui_evidence"]] if step.get("ui_evidence") else [])


def case_pictures(stage, case, anchor):
    """Select only inside this case attempt. Missing semantic fields keep legacy references independent."""
    rows, winners = {}, {}
    for position, step in enumerate(case["steps"], 1):
        check_image_identity(stage, case, step)
        entries = rows[position] = []
        for number, image in enumerate(step_images(step), 1):
            if image.get("point") in {"failure", "blocked", "unknown", "timeout"}:
                image = {**image, "role": "key"}  # Bound to this capture, independent of the verdict recorded later.
            if (image.get("path") or image.get("data_uri")) and not re.fullmatch(
                    r"(?:sha256:)?[0-9a-fA-F]{64}", str(image.get("sha256", ""))):
                raise ValueError("E_STAGE_IMAGE_DIGEST_REQUIRED")
            ref = f"{anchor}-step-{position}-image-{number}"
            caption = image.get("caption") or step.get("action") or step.get("step_id") or "截图"
            group = (image.get("object_ref"), image.get("point"), image.get("moment_ref", position),
                     image.get("state_ref") or image.get("observation"))
            if ("moment_ref" in image and not isinstance(group[2], str)
                    or not all(isinstance(field, str) and field.strip() for field in (group[0], group[1], group[3]))):
                group = ref
            resolved = resolve_image_source(image)
            picture = render_image_evidence(image, caption, inline_metadata=False, resolved_source=resolved)
            available = resolved[0] is not None
            entries.append((ref, group, image, caption, picture, available))
            if available and image.get("role") == "key" and image.get("support", "direct") == "direct":
                preferred = image.get("preferred") is True
                if group not in winners or preferred > winners[group][0]:
                    winners[group] = (preferred, ref)
    return rows, {group: ref for group, (_, ref) in winners.items()}


def render_step(step, anchor, entries, winners):
    action = step.get("action") or step.get("step_id") or "步骤"
    title = escaped(action)
    key_images, ordinary, index, related = [], [], [], set()
    for ref, group, image, caption, picture, available in entries:
        label = escaped(caption)
        source = escaped(image.get("source_ref") or image.get("path") or ref)
        index_label = f'{title} · {label} · {source}'
        if image.get("role") != "key":
            ordinary.append(f'<div id="{ref}">{picture}</div>')
        elif not available:
            key_images.append(f'<div id="{ref}">{picture}</div>')
        elif winners.get(group) == ref:
            goal = image.get("final_goal") if image.get("point") == "receipt" else None
            if isinstance(goal, str) and goal.strip():
                label += f' · 回执同时证明最终目标「{escaped(goal)}」'
            key_images.append(f'<figure id="{ref}">{picture}<figcaption>{label}</figcaption></figure>')
        else:
            index.append(f'<li id="{ref}">{index_label}{picture}</li>')
            if winners.get(group):
                related.add(winners[group])
            else:
                key_images.append(f'<p>仅有辅助画面，无法从图中核对该状态。<a href="#{ref}">{label}</a></p>')
            continue
        index.append(f'<li><a href="#{ref}">{index_label}</a></li>')
    for representative in sorted(related):
        if not representative.startswith(anchor + "-image-"):
            key_images.append(f'<p><a href="#{representative}">查看同一状态代表图</a></p>')
    key = key_images or step.get("key_reason") or step.get("status") in {"failed", "blocked", "error", "unknown"}
    navigation = f'<li><a href="#{anchor}">{title}</a></li>' if key else ""
    explanations = "".join(f'<dt>{label}</dt><dd>{escaped(step[field])}</dd>'
                           for field, label in (("expected_result", "预期"), ("actual_result", "实际"),
                                                ("reason", "原因"), ("key_reason", "关键依据")) if step.get(field))
    pictures = "".join(key_images)
    if ordinary:
        pictures += (f'<details class="ordinary-images"><summary>查看步骤截图（{len(ordinary)} 张）</summary>'
                     f'<div class="thumbnails">{"".join(ordinary)}</div></details>')
    if not entries and recorded_action(step):
        pictures = '<p class="evidence-limit">本次步骤无可审阅截图，无法从画面核对实际状态。</p>'
    status = escaped(status_label(step.get("status", "")))
    if step.get("status") == "skipped" and step.get("reason") == "predecessor_failed":
        status += " · 前序失败，未执行"
    return navigation, (f'<li id="{anchor}"><div class="step-head"><h3>{title}</h3><span>{status}</span></div>'
                        f'<dl>{explanations}</dl>{pictures}</li>'), "".join(index)


def render_stage_html(stage, run_id, cases, *, folder=None, origin=None):
    from stage_footer import agent_footer
    footer = agent_footer(stage, run_id, cases, folder, origin or {})
    title = {"playwright": "Playwright 正式执行报告", "midscene": "Midscene 探索报告"}[stage]
    contents, sections, diagnostics = [], [], []
    for index, case in enumerate(cases, 1):
        label = escaped(case.get("case_id") or case["node_id"])
        if case.get("branch_id") and case["branch_id"] != case.get("case_id"):
            label += " / " + escaped(case["branch_id"])
        anchor = f"case-{index}"
        links, rows, image_index = [], [], []
        entries, winners = case_pictures(stage, case, anchor)
        for position, step in enumerate(case["steps"], 1):
            link, row, step_index = render_step(step, f"{anchor}-step-{position}", entries[position], winners)
            links.append(link)
            rows.append(row)
            image_index.append(step_index)
        attempt = escaped(case.get("attempt_ref", ""))
        attempt_label = f" · 尝试 {attempt}" if attempt else ""
        contents.append(f'<li><a href="#{anchor}">{label} · {escaped(case["node_id"])}{attempt_label}</a>'
                        f'<ul>{"".join(links)}</ul></li>')
        identity = " · ".join(escaped(case[k]) for k in ("node_id", "session_id", "run_id", "attempt_ref") if case.get(k))
        last = next((step for step in reversed(case["steps"]) if recorded_action(step)), None)
        last_action = (last.get("action") or last.get("step_id") or "未命名步骤") if last else "本次无已记录动作"
        sections.append(f'<section id="{anchor}"><header><h2>{label}</h2><strong>{escaped(status_label(case["status"]))}</strong>'
                        f'</header><p class="identity">{identity}</p><p>{escaped(case.get("reason", ""))}</p>'
                        f'<p>最后记录的动作 · {escaped(last_action)}</p><ol class="steps">{"".join(rows)}</ol></section>')
        replay = case.get("native_replay_url", "")
        replay_link = (f'<a href="{escaped(replay)}">查看本地原始回放</a>' if replay.startswith("file:///") else "")
        evidence = escaped(json.dumps(case.get("evidence_index", {}), indent=2, ensure_ascii=False))
        diagnostics.append(f'<h3>{label}{attempt_label}</h3>{replay_link}<ul>{"".join(image_index)}</ul><pre>{evidence}</pre>')
    count = len({(case.get("case_id") or case["node_id"], case.get("branch_id")) for case in cases})
    count_label = f"{count} 条用例" + (f" · {len(cases)} 次尝试" if count != len(cases) else "")
    css = (Path(__file__).resolve().parents[1] / "assets" / "stage-report.css").read_text(encoding="utf8")
    return install_image_viewer(
        f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width, initial-scale=1"><title>{title}</title><style>{css}</style></head>'
        f'<body><main class="report"><header class="hero"><h1>{title}</h1><p>{count_label} · {escaped(run_id)}</p>'
        f'</header><nav aria-label="用例与关键节点"><h2>用例与关键节点</h2><ol>{"".join(contents)}</ol></nav>'
        f'{"".join(sections)}<details class="sources"><summary>证据索引与运行来源</summary>{"".join(diagnostics)}'
        f'</details>{footer}</main></body></html>')


def publish_stage_report(stage, run_id, cases, output_dir, *, origin=None):
    """Call only after the stage adapter has checked source identity and finalized evidence."""
    from generate_report import scan_sensitive

    if scan_sensitive([run_id, cases]):
        raise ValueError("E_STAGE_SENSITIVE_FIELDS")
    output = Path(output_dir).resolve()
    html_document = render_stage_html(stage, run_id, cases, folder=output, origin=origin)
    local_io_path(output).mkdir(parents=True, exist_ok=True)
    report = output / "report.html"
    summary = output / "execution-summary.json"
    index = output / "evidence-index.json"
    identities = [{key: case[key] for key in ("case_id", "branch_id", "node_id", "session_id", "run_id", "attempt_ref",
                                               "status", "reason", "run_result_hash") if key in case} for case in cases]
    for path, rows in ((summary, identities), (index, [case.get("evidence_index", {}) for case in cases])):
        atomic_text(path, json.dumps(dict(stage=stage, run_id=run_id, cases=rows), ensure_ascii=False, indent=2))
    atomic_text(report, html_document)  # The entry is published after rendering and provenance checks complete.
    return dict(report_html=str(report), report_url=report.as_uri(), execution_summary=str(summary), evidence_index=str(index))
