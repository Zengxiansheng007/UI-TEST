"""Publish the read-only inventory for engineers and downstream governance tools."""
from html import escape
from contextlib import closing
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .artifact_inventory import LABELS, inventory_project
from .catalog_html import render_catalog
from .run_catalog import render_database_catalog
from .asset_revision import replace
from .codex_dispatch_state import publish
from .file_lock import exclusive_file_lock
from .path_planner import validate_existing_path_containment


def owner_label(owner):
    return " / ".join(str(owner[key]) for key in ("stage_id","linked_stage_id","legacy_batch","legacy_report","case_id",
                         "branch_id","attempt_ref","step_id","asset_id","dependency_id","version") if owner.get(key))


def inventory_html(data):
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>项目产物盘点</title>',
             '<style>body{font:16px system-ui;margin:2em auto;max-width:80em}td,th{padding:.4em;text-align:left}'
             'td{vertical-align:top}table{border-collapse:collapse}tr{border-bottom:1px solid #ccc}</style>',
             '<a href="../index.html">项目运行目录</a><h1>项目产物盘点</h1><p>盘点时间 '+escape(data["generated_at"])+'</p>']
    status = {"stage_referenced":"阶段引用","named_legacy":"已点名历史批次","inventory_only":"仅盘点"}
    for group in data["categories"]:
        category = group["category"]
        parts.append(f'<details><summary>{LABELS[category]} · {group["count"]} 个文件 · {group["bytes"]} 字节</summary>'
                     '<table><tr><th>文件</th><th>字节</th><th>范围</th><th>已知使用方及步骤</th></tr>')
        for row in data["files"]:
            if row["category"]!=category:
                continue
            users = "<br>".join(escape(owner_label(owner)) for owner in row["consumers"]) or "未知"
            scope = " · ".join([status[row["eligibility"]],*row["legacy_batches"]])
            ref = quote(row["path"],safe="/")
            parts.append(f'<tr><td><a href="../{ref}">{escape(row["path"])}</a></td><td>{row["size"]}</td>'
                         f'<td>{escape(scope)}</td><td>{users}</td></tr>')
        parts.append("</table></details>")
    if data["issues"]:
        parts.append("<h2>待核引用</h2><ul>")
        for issue in data["issues"]:
            text = " · ".join(filter(None,(owner_label(issue),issue.get("path"),issue["reason"])))
            parts.append("<li>"+escape(text)+"</li>")
        parts.append("</ul>")
    return "\n".join([*parts,"</html>"])


def publish_inventory(project):
    root = Path(project).resolve(strict=True)
    folder = root / "治理"
    lock = folder / ".inventory.lock"
    for target in (lock,folder/"inventory.json",folder/"inventory.html"):
        validate_existing_path_containment(root,target)
    with exclusive_file_lock(lock):
        data = inventory_project(root)
        publish(folder/"inventory.json",data)
        replace(folder/"inventory.html",inventory_html(data).encode("utf8"))
    refresh_navigation(root)
    return folder/"inventory.html"


def refresh_navigation(root):
    database = root / "runs.sqlite3"
    for target in (database, root / "index.html", root / ".catalog.lock"):
        validate_existing_path_containment(root, target)
    if database.is_file():
        with exclusive_file_lock(root / ".catalog.lock"), closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            render_database_catalog(root, db)
    else:
        with exclusive_file_lock(root / ".catalog.lock"):
            page = root / "index.html"
            if page.exists():
                with page.open("rb") as stream:
                    generated = stream.read(128).startswith('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>项目运行目录</title>'.encode())
                if not generated:
                    return
            if database.exists():
                return
            with_cases = (root / "current-cases.json").is_file() or (root / "用例").is_dir()
            if not with_cases:
                render_catalog(root, [], [])
                return
        from .run_catalog import refresh_catalog
        refresh_catalog(root)  # Acquire the catalog lock after releasing the navigation lock.
