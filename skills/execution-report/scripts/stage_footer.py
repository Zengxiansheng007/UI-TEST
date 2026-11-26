"""Offline navigation from a sealed stage to the precise execution originals."""
from html import escape
import os
from pathlib import Path
from urllib.parse import quote


def agent_footer(stage, run_id, cases, folder, origin, source_root=None):
    project = folder.parent.parent if folder and folder.parent.name == "运行" else None

    def link(path, title, *, fragment="", generated=False):
        if not folder or not path:
            return escape(title) + "未提供"
        path = Path(path)
        target = path.resolve() if path.is_absolute() else ((project or folder) / path).resolve()
        allowed = (source_root if source_root and not generated else None) or project or folder
        if not target.is_relative_to(allowed) or (not generated and not target.is_file()):
            return escape(title) + "缺件或超出项目范围"
        if target.drive != folder.drive:
            url = target.as_uri() + fragment
        else:
            url = "./" + quote(Path(os.path.relpath(target, folder)).as_posix(), safe="/") + fragment
        return f'<a href="{escape(url,quote=True)}">{escape(title)}</a>'

    parts = ['<footer id="agent"><h2>阶段运行与原件</h2><p>阶段运行号 <code>' + escape(run_id) + '</code></p>']
    if folder:
        parts.append('<p>' + link(folder / "evidence-index.json", "本阶段证据索引", generated=True) + '</p>')
    if stage == "midscene" and project:
        parts.append('<p>' + link(project / "index.html", "查看关联正式执行", fragment="#stage-" + quote(run_id, safe=""), generated=True) + '</p>')
    elif stage == "playwright":
        if origin.get("kind") == "exploration":
            parts.append('<p>来源探索 · ' + link(origin["report"], origin["stage_id"]) + ' · '
                         + link(origin["observations"], "探索观察原件") + ' · ' + link(folder / "start.json", "阶段来源记录") + '</p>')
        else:
            status = "独立执行" if origin.get("kind") == "independent" else "来源未知"
            parts.append('<p>' + status + (' · ' + link(folder / "start.json", "阶段来源记录") if folder and (folder / "start.json").is_file() else '') + '</p>')
    for case in cases:
        identity = " / ".join(str(case[key]) for key in ("case_id","branch_id","node_id","attempt_ref") if case.get(key))
        binding = case.get("binding") or {}
        parts.append('<h3>' + escape(identity) + '</h3>')
        if binding:
            parts.append('<p>实际版本 <code>' + escape(binding["version"]) + '</code> · ' + link(binding["entry"], "执行时入口")
                         + ' · SHA-256 ' + escape(binding["sha256"]) + '</p>')
            for dep in binding["dependencies"]:
                parts.append('<p>项目依赖 ' + link(dep["entry"], dep["source"]) + ' · ' + escape(dep["sha256"]) + '</p>')
        else:
            parts.append('<p>' + ("未执行，无实际版本" if case.get("status") in {"not_executed","not-executed"} else "缺少执行时版本绑定") + '</p>')
        parts.append('<p>' + link(case.get("execution_source"), "执行原件") + ' · ' + link(case.get("evidence_source"), "证据索引") + '</p>')
    return "".join(parts) + "</footer>"
