"""Read legacy case releases and HTML in place within explicitly selected directories."""
import os
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import url2pathname

from .case_contracts import validate_document
from .path_planner import validate_existing_path_containment
from .release_verifier import verify_release
from .strict_json import load_strict_json


CONFIG = "legacy-sources.json"
PRIVATE = {"_private", ".git", ".codex", "__pycache__"}


class ReportLinks(HTMLParser):
    """Collect local link targets with the document's original base URL."""

    def __init__(self):
        super().__init__()
        self.base = None
        self.targets = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if not value:
                continue
            if tag == "base" and key == "href":
                if self.base is None:
                    self.base = value
            elif key in {"href", "src"} and not value.startswith(("#", "data:")):
                self.targets.append(value)


def _report_reason(path, roots, files):
    links = ReportLinks()
    links.feed(path.read_text(encoding="utf-8-sig", errors="replace"))
    base = urljoin(path.as_uri(), links.base or "")  # Resolve as the original offline viewer would.
    problems = []
    for raw in links.targets:
        url = urlsplit(urljoin(base, raw))
        if url.scheme != "file" or url.netloc not in {"", "localhost"}:
            continue
        target = Path(os.path.normpath(url2pathname(url.path)))
        if not any(target.is_relative_to(folder) for folder in roots):
            problems.append("引用超出配置范围 " + urlsplit(raw).path)
        elif target not in files:
            problems.append("引用失链 " + urlsplit(raw).path)
    return "；".join(dict.fromkeys(problems))


def discover_legacy(project_root):
    root = Path(project_root).resolve(strict=True)
    config = root / CONFIG
    validate_existing_path_containment(root, config)
    settings = load_strict_json(config) if config.exists() else {"directories": []}
    directories = settings.get("directories") if isinstance(settings, dict) else None
    if not isinstance(directories, list) or not all(isinstance(item, str) and item.strip() for item in directories):
        raise ValueError("E_LEGACY_DIRECTORIES_CONFIG")
    files, folders, blocked, rows = set(), set(), set(), {}

    def record(path, source, kind, status, reason="", case_id="", branch_id="", version=""):
        key = path.relative_to(root).as_posix()
        rows[key] = dict(path=key, source=source.relative_to(root).as_posix(), kind=kind,
                         status=status, reason=reason, case_id=case_id, branch_id=branch_id, version=version)

    def readable(path):
        try:
            validate_existing_path_containment(root, path)
            return not PRIVATE.intersection(p.casefold() for p in path.relative_to(root).parts)
        except (ValueError, OSError):
            return False

    def walk_error(error):
        failed = Path(error.filename)
        blocked.add(failed)
        record(failed, config, "directory", "pending", "目录不可读取")

    if (root / "用例").is_dir():
        directories = [*directories, "用例"]
    for item in directories:
        relative = Path(item)
        if relative.anchor or ".." in relative.parts or not relative.parts:
            raise ValueError("E_LEGACY_SCOPE")
        folder = root / relative
        if not readable(folder):
            raise ValueError("E_LEGACY_SCOPE")
        folders.add(folder)
        if not folder.is_dir():
            record(folder, config, "directory", "missing", "配置的目录缺失")
            continue
        for here, children, names in os.walk(folder, onerror=walk_error):
            here = Path(here)
            for child in list(children):
                if not readable(here / child):
                    blocked.add(here / child)
                    children.remove(child)
            for name in names:
                target = here / name
                if readable(target):
                    files.add(target)
                else:
                    blocked.add(target)

    scripts = {p for p in files if p.suffix.lower() == ".py"}
    counts = Counter(p.name.casefold() for p in scripts)
    for path in sorted(scripts):
        reason = "同名脚本归属待核" if counts[path.name.casefold()] > 1 else "缺少可核实的生效记录"
        record(path, config, "script", "pending", reason)
    for path in sorted(p for p in files if p.suffix.lower() in {".htm", ".html"}):
        try:
            reason = _report_reason(path, folders, files)
            record(path, config, "report", "broken" if reason else "historical", reason)
        except (OSError, ValueError) as error:
            record(path, config, "report", "pending", "无法读取报告引用 " + type(error).__name__)

    pointers = {}
    for pointer in sorted(p for p in files if p.name == "active.json"):
        try:
            data = load_strict_json(pointer)
            if validate_document(data, "active-pointer-v2.schema.json"):
                raise ValueError("指针格式无效")
            manifest = pointer.parent / data["manifest_ref"]
            if manifest not in files:
                raise ValueError("指针失链或超出配置范围 " + data["manifest_ref"])
            if manifest.parent.name != data["build_fingerprint"].split(":")[1]:
                raise ValueError("指针目录与生效版本不一致")
            pointers[manifest] = (pointer, data)
        except (OSError, ValueError) as error:
            record(pointer, pointer, "pointer", "broken", str(error))

    for manifest in sorted(p for p in files if p.name == "manifest.json" and p.parent.parent.name == "releases"):
        release = manifest.parent
        script = release / "playwright-test.py"
        pointer, active = pointers.get(manifest, (manifest, None))
        try:
            if any(p.is_relative_to(release) for p in blocked):
                raise ValueError("发布内包含不可读取或越界引用")
            data = load_strict_json(manifest)
            if validate_document(data, "case-manifest-v2.schema.json"):
                raise ValueError("发布清单格式无效")
            state = verify_release(release, active_pointer=active)
            issues = [i["code"] + " " + i["path"] for i in state["issues"]]
            if release.name != data["build_fingerprint"].removeprefix("sha256:"):
                issues.append("发布目录与版本不一致")
            branch = release.parent.parent
            if branch.parent.name == "branches" and (branch.name != data["branch_id"] or branch.parent.parent.name != data["case_id"]):
                issues.append("用例分支目录与发布身份不一致")
            if "playwright-test.py" not in data["artifacts"]:
                issues.append("清单未登记正式脚本")
            status = "pending" if issues else ("current" if active else "historical")
            if script not in files:
                status = "missing"
                issues.append("正式脚本缺件")
            record(script, pointer, "script", status, "；".join(issues),
                   data["case_id"], data["branch_id"], data["build_fingerprint"])
        except (ValueError, OSError, TypeError) as error:
            record(manifest, pointer, "manifest", "pending", "发布清单待核 " + str(error))

    # Two independently valid installations can disagree about a branch's active entry.
    by_branch = defaultdict(list)
    for row in rows.values():
        if row["status"] == "current":
            by_branch[row["case_id"], row["branch_id"]].append(row)
    for matches in by_branch.values():
        if len(matches) > 1:
            for row in matches:
                row.update(status="pending", reason="多个生效记录指向同一用例分支，归属待核")
    for row in rows.values():
        if row["kind"] == "script" and row["status"] == "historical":
            matches = by_branch[row["case_id"], row["branch_id"]]
            if len(matches) != 1:
                row.update(status="pending", reason="发布完整，但缺少唯一可核实的生效记录")
    return [rows[key] for key in sorted(rows)]
