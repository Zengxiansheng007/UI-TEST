"""Static, locally filterable rendering of the project's SQL catalog."""
import json
import os
import sys
from datetime import datetime, timezone
from html import escape
from itertools import groupby
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote


def label(value):
    return escape(str(value)) if value is not None else "未知"


def link(root, ref, title):
    if not ref:
        return ""
    path = (root / ref).resolve()
    if not path.is_relative_to(root):
        return label(ref)
    if not path.is_file():
        return label(title + "（缺件） " + ref)
    return f'<a href="./{quote(ref, safe="/")}">{label(title)}</a>'


def historical_link(path, title):
    return f'<a href="{escape(Path(path).as_uri(), quote=True)}">{label(title)}</a>' if path else ""


def render_catalog(root, rows, legacy, downstream=None, current=(), archives=None):
    fields = (("from","开始日自","date"),("to","开始日至","date"),("stage_type","阶段","text"),
              ("case_id","用例","text"),("branch_id","分支","text"),("status","状态","text"),("version","实际版本","text"))
    html = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>项目运行目录</title>',
            '<style>body{font:16px system-ui;max-width:72rem;margin:2rem auto;padding:0 1rem}label, a{margin-right:1rem}label{display:inline-block}input{display:block;width:10rem}section,details{margin:1rem 0}summary{cursor:pointer}</style>',
            '<h1>项目运行目录</h1><p>更新时间 ' + datetime.now(timezone.utc).astimezone().isoformat() + '</p>']
    if (root / "治理/inventory.html").is_file():
        html.append('<p><a href="./%E6%B2%BB%E7%90%86/inventory.html">查看项目产物盘点</a></p>')
    from ui_test_core.suite import selected_suite
    entry = selected_suite().root / "scripts" / "project_governance.py"
    command = "& " + " ".join("'" + value.replace("'", "''") + "'" for value in (sys.executable, str(entry), "preview", str(root)))
    html.append('<p>用 PowerShell 手动生成待审清单 <code>' + label(command) + '</code></p>')
    if (root / "治理/previews.html").is_file():
        html.append('<p><a href="./%E6%B2%BB%E7%90%86/previews.html">历次待审清单</a></p>')
    if current:
        html.append('<h2>当前用例</h2><label>按业务名称或编号查找<input id="current-filter" type="search"></label><ul id="current-cases">')
        for case in current:
            identity = " / ".join([case["case_id"],case["branch_id"]])
            entry = link(root,case["entry"],"打开当前脚本") if case["status"]=="current" else ""
            node = label(case["node_id"]) if case["node_id"] else ""
            html.append(f'<li>{label(case["display_name"])} · {label(identity)} · {entry} {node} · {label(case["reason"])}</li>')
        html.append('</ul>')
    html.append('<form>')
    for field,title,kind in fields:
        values = sorted({row[field] for row in rows if field in row.keys() and row[field]})
        options = ''.join(f'<option value="{label(v)}"></option>' for v in values)
        html.append(f'<label>{title}<input type="{kind}" name="{field}" list="v-{field}"></label><datalist id="v-{field}">{options}</datalist>')
    html.append('<button type="reset">清除筛选</button></form>')
    for stage_id, group in groupby(rows, key=lambda row: row["stage_id"]):
        records = list(group)
        stage = records[0]
        history = (archives or {}).get(stage_id, [])
        report_link = historical_link(history[0]["reader"], "历史阶段报告") if history else link(root, stage["report_ref"], "阶段报告")
        milestone = "阶段收尾" if stage["ended_at"] else "执行中，尚无收尾记录"
        html.append(f'<section id="stage-{label(stage_id)}"><h2>{label(stage_id)}</h2><p>登记进度 · {milestone} · {label(stage["stage_type"])} · {label(stage["stage_status"])} · '
                    f'{label(stage["started_at"])} 至 {label(stage["ended_at"])} · 项目开始日 {label(stage["local_date"])} '
                    + report_link + '</p>')
        states = {"online":"介质在线","offline":"介质离线","changed":"归档内容已变化","unavailable":"介质不可读"}
        for checksum, items in groupby(history, key=lambda r: r["manifest_sha256"]):
            archive = next(items)
            html.append(f'<p>已释放 · {label(states[archive["media_status"]])} · 归档位置 {label(archive["archive_dir"])} '
                        f'· 清单 SHA-256 {label(checksum)} ' + historical_link(archive["reader"], "打开历史原件") + '</p>')
        if stage["stage_type"] == "midscene":
            related = []
            for child, ref in sorted((downstream or {}).get(stage_id, [])):
                saved = (archives or {}).get(child, [])
                if saved:
                    related.append(historical_link(saved[0]["reader"], child) or label(child) + "（介质离线）")
                else:
                    related.append(link(root, ref, child) if ref else label(child) + "（报告待生成）")
            html.append("<p>关联正式执行 · " + (" · ".join(related) if related else "尚无已登记来源") + "</p>")
        for row in records:
            attrs = ' '.join(f'data-{key}="{escape(str(row[key] or ""))}"' for key in
                             ("local_date","stage_type","case_id","branch_id","status","version"))
            attempt = "尝试 " + label(row["attempt_ref"]) if row["attempt_ref"] else "无尝试记录"
            historical = next((item for item in history if all(item[k] == row[k] for k in
                               ("case_id","branch_id","attempt_ref","version"))), None)
            binding = ""
            if historical is not None:
                binding = historical_link(historical["script_file"], "执行时入口") or "接入归档介质可打开执行时入口"
            elif row["entry"]:
                deps = [link(root, dep["entry"], dep["source"]) + " " + label(dep["sha256"])
                        for dep in json.loads(row["dependencies"])]
                binding = (link(root,row["entry"],"执行时入口") + " " + label(row["source"])
                           + " · 测试节点 " + label(row["node_id"]) + " · SHA-256 " + label(row["sha256"])
                           + (" · 发布 " + label(row["release"]) if row["release"] else "")
                           + (" · 项目依赖 " + "；".join(deps) if deps else ""))
            elif row["attempt_ref"]:
                binding = "缺少执行时版本绑定"
            execution = historical_link(historical["execution_file"], "执行原件") if historical is not None else link(root,row["execution_ref"],"执行原件")
            evidence = historical_link(historical["evidence_file"], "证据索引") if historical is not None else link(root,row["evidence_ref"],"证据索引")
            if historical is None and not evidence:
                evidence = "证据索引未提供"
            html.append(f'<details {attrs}><summary>{label(row["case_id"])} / {label(row["branch_id"])} · {attempt} · {label(row["status"])}</summary>'
                        f'<p>实际版本 {label(row["version"])} · {execution} {evidence}</p><p>{binding}</p></details>')
        html.append('</section>')
    legacy = list(legacy)
    if legacy:
        html.append('<h2>历史资料</h2><ul>')
        states = dict(current="生效", historical="历史", pending="归属待核", missing="缺件", broken="失链")
        for row in legacy:
            html.append('<li>' + ' · '.join([label(row["case_id"]),label(row["branch_id"]),label(row["version"]),
                        label(states.get(row["status"],row["status"])),label(row["reason"]),link(root,row["path"],row["path"]),
                        link(root,row["source"],"来源")]) + '</li>')
        html.append('</ul>')
    html.append("""<script>
document.querySelector('#current-filter')?.addEventListener('input',event=>{
  const query=event.target.value.trim().toLowerCase();
  for (const row of document.querySelectorAll('#current-cases li')) row.hidden=!row.textContent.toLowerCase().includes(query);
});
const form = document.querySelector('form');
function filter() {
  const f = Object.fromEntries(new FormData(form));
  for (const section of document.querySelectorAll('section')) {
    let visible = false;
    for (const row of section.querySelectorAll('details')) {
      const day = row.dataset.local_date;
      row.hidden = Boolean((f.from && (!day || day < f.from)) || (f.to && (!day || day > f.to)) ||
        ['stage_type','case_id','branch_id','status','version'].some(key => f[key] && f[key] !== row.dataset[key]));
      visible ||= !row.hidden;
    }
    section.hidden = !visible;
  }
}
form.addEventListener('submit', event => event.preventDefault());
form.addEventListener('input',filter);
form.addEventListener('reset',() => setTimeout(filter,0));
</script></html>""")
    with NamedTemporaryFile("w", encoding="utf8", delete=False, dir=root, prefix=".cat-") as stream:
        tmp = Path(stream.name)
        stream.write("\n".join(html))
    try:
        os.replace(tmp, root / "index.html")
    finally:
        tmp.unlink(missing_ok=True)
