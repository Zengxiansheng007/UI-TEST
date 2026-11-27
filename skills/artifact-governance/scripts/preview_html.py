"""Offline HTML views over immutable project preview records."""
import re
from html import escape
from urllib.parse import quote

from .artifact_inventory import LABELS
from ui_test_core.path_planner import validate_existing_path_containment
from ui_test_core.strict_json import load_strict_json

DECISIONS = {"retain":"整阶段保留", "candidate":"候选", "review":"待核，保留现场","inventory_only":"仅盘点"}
STYLE = "<style>body{font:16px system-ui;line-height:1.5;max-width:78em;margin:2em auto;padding:0 1em}section,details{margin:1em 0}table{border-collapse:collapse}td,th{padding:.4em;text-align:left;border-bottom:1px solid #ccc}summary{cursor:pointer}</style>"


def label(value):
    return escape(str(value)) if value is not None else "未知"


def owners(row):
    keys = ("stage_id","linked_stage_id","legacy_batch","legacy_report","case_id","branch_id","attempt_ref","step_id","asset_id","dependency_id")
    return "<br>".join(" / ".join(label(entry[key]) for key in keys if entry.get(key))
                       for entry in row["consumers"]) or "未归属"


def file_table(data, paths):
    states = {"inventory_only":"仅盘点", "named_legacy":"点名历史批次", "stage_referenced":"阶段引用"}
    rows = ["<table><tr><th>原件</th><th>字节数</th><th>范围</th><th>使用方与步骤</th></tr>"]
    for path in paths:
        item = data["files"][path]
        rows.append(f'<tr><td><a href="../../{quote(path, safe="/")}">{label(path)}</a></td>'
                    f'<td>{item["size"]}</td><td>{states[item["eligibility"]]} '
                    f'{label("、".join(item["legacy_batches"]))}</td><td>{owners(item)}</td></tr>')
    return "".join([*rows, "</table>"])


def preview_html(data):
    dest = label(data["archive_destination"]) if data["archive_destination"] else "未配置"
    policy = data["policy"]
    rows = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>阶段治理待审清单</title>', STYLE,
            '<a href="../../index.html">项目运行目录</a> · <a href="../previews.html">历次待审清单</a>',
            '<h1>阶段治理待审清单</h1>',
            f'<p>项目 {label(data["project"])} · 生成时间 {label(data["generated_at"])} · 清单 {label(data["preview_id"])}</p>',
            f'<p>归档目的地 {dest} · 保留 {policy["retention_days"]} 天 · 每个分支每种阶段保留最近 {policy["recent_per_branch"]} 次</p>']
    for group in data["categories"]:
        category=group["category"]
        rows.append(f'<details><summary>{LABELS[category]} · {group["count"]} 个文件 · {group["bytes"]} 字节</summary>')
        rows.append(file_table(data, (p for p,item in data["files"].items() if item["category"]==category)))
        rows.append("</details>")
    for sid, stage in sorted(data["stages"].items()):
        rows.append(f'<section><h2>{label(sid)} · {DECISIONS[stage["decision"]]}</h2>'
                    f'<p>{label(stage.get("stage_type"))} · 阶段状态 {label(stage.get("status"))} · '
                    f'结束 {label(stage.get("ended_at"))} · 目的地 {dest}</p><ul>')
        for r in stage["reasons"]:
            values = [r.get(key) for key in ("case_id","branch_id","attempt_ref","step_id","path")]
            rows.append("<li>" + " · ".join(label(v) for v in [r["reason"], *values] if v) + "</li>")
        rows.append("</ul>")
        for key, title in (("proposed_release","拟释放工作副本"),("keep_files","留用工作副本")):
            paths = stage[key]
            rows.append(f"<details><summary>{title} · {len(paths)} 个文件</summary>")
            if paths:
                if key == "proposed_release":
                    rows.append("<p>共享副本须待列出的所有使用阶段获批并完成核验后才能释放。</p>")
                rows.append(file_table(data, paths))
            rows.append("</details>")
        rows.append("</section>")
    unassigned = [issue for issue in data["issues"] if issue.get("stage_id") not in data["stages"]]
    if unassigned:
        rows.append("<h2>其他待核引用</h2><ul>")
        for issue in unassigned:
            rows.append("<li>" + " · ".join(label(issue[key]) for key in ("asset_id","path","reason") if issue.get(key)) + "</li>")
        rows.append("</ul>")
    return "\n".join([*rows, "</html>"])


def history_html(root, folder):
    records = []
    unavailable = []
    for page in folder.glob("*.html"):
        if not re.fullmatch("[a-f0-9]{20}", page.stem):
            continue
        record = page.with_suffix(".json")
        try:
            for target in (page, record):
                validate_existing_path_containment(root, target)
            data = load_strict_json(record)
            if data["preview_id"] != page.stem or not isinstance(data["generated_at"], str):
                raise ValueError("E_PREVIEW_HISTORY_ID")
            records.append((data["generated_at"],page.name,data["preview_id"]))
        except (OSError, ValueError, TypeError, KeyError):
            unavailable.append(page.stem)
    rows = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>历次待审清单</title>',STYLE,
            '<a href="../index.html">项目运行目录</a><h1>历次待审清单</h1><ul>']
    for created, name, identity in sorted(records,reverse=True):
        rows.append(f'<li><a href="{quote("清单/"+name)}">{label(created)} · {label(identity)}</a></li>')
    for identity in sorted(unavailable):
        rows.append("<li>" + label(identity) + " · 清单记录待核</li>")
    return "\n".join([*rows,"</ul></html>"])
