"""Build and publish a non-destructive, stage-scoped retention preview from project facts."""
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import file_digest, sha256
import os
import re
from pathlib import Path
from uuid import uuid4

from .artifact_inventory import ProjectInventory, private
from .artifact_layout import checked_path
from .asset_revision import encoded, replace
from .file_lock import exclusive_file_lock
from .inventory_report import refresh_navigation
from .path_planner import validate_existing_path_containment
from .preview_html import history_html, preview_html
from .strict_json import load_strict_json


def read_policy(settings):
    policy = {key: settings.get(key, default) for key, default in
              (("retention_days", 30), ("recent_per_branch", 3))}
    if any(type(value) is not int or value < 0 for value in policy.values()):
        raise ValueError("E_RETENTION_POLICY: 保留天数及最近次数应为非负整数")
    for key in ("protected_stages", "protected_files"):
        entries = settings.get(key, {})
        if not isinstance(entries, dict) or not all(name.strip() and isinstance(reason, str) and reason.strip()
                                                    for name, reason in entries.items()):
            raise ValueError("E_RETENTION_PROTECTION: 人工保护应指定对象和原因")
        policy[key] = dict(entries)
    paths = {}
    for name, reason in policy["protected_files"].items():
        ref = Path(name)
        if ref.anchor or ".." in ref.parts or not ref.parts or private(ref):
            raise ValueError("E_RETENTION_PROTECTION_PATH")
        paths[ref.as_posix()] = reason
    policy["protected_files"] = paths
    return policy


def instant(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.utcoffset() is not None:
            return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def reason(code, text, **scope):
    return dict(code=code, reason=text, **scope)


def rank_stages(stages, now, count):
    by_branch, ends, running = defaultdict(list), {}, set()
    for sid, stage in stages.items():
        cases = stage["cases"]
        if stage.get("status") == "running" or any(a["status"] == "running" for c in cases for a in c["attempts"]):
            running.add(sid)
            continue
        end = instant(stage.get("ended_at"))
        start = instant(stage.get("started_at"))
        if not end or end > now or (start and end < start):
            continue
        ends[sid] = end
        if stage["disposition_scope"] == "inventory_only":
            continue
        for case in cases:
            if any(a["status"] not in {"not_executed", "not-executed"} for a in case["attempts"]):
                key = (stage["stage_type"], case["case_id"], case["branch_id"])
                by_branch[key].append((end, sid))
    recent = defaultdict(list)
    for (kind, case, branch), rows in sorted(by_branch.items()):
        for rank, (_, sid) in enumerate(sorted(set(rows), reverse=True)[:count], 1):
            recent[sid].append(reason("recent", f"{case} / {branch} · {kind} 最近第 {rank} 次已收尾执行",
                                      case_id=case, branch_id=branch, stage_type=kind, rank=rank))
    return ends, running, recent


def build_preview(project, *, now=None, archived_files=None):
    root = Path(project).resolve(strict=True)
    now = datetime.now(timezone.utc) if now is None else now
    if now.utcoffset() is None:
        raise ValueError("E_RETENTION_CLOCK")
    now = now.astimezone(timezone.utc)
    inventory = ProjectInventory(root,archived_files=archived_files)
    settings = inventory.settings("governance-settings.json")
    policy = read_policy(settings)
    protected_files = {Path(key): value for key, value in policy["protected_files"].items()}
    destination = settings.get("archive_destination")
    if destination:
        dest = Path(destination)
        if not dest.is_absolute() or dest.as_posix().startswith("//") or ".." in dest.parts or dest.is_relative_to(root):
            raise ValueError("E_RETENTION_ARCHIVE_ROOT: 归档位置应为项目外的本地绝对路径")
        destination = str(dest)
    facts = inventory.build()
    stages = facts["stages"]
    for sid in facts["legacy_batches"]:
        stages.setdefault(sid, dict(stage_id=sid, disposition_scope="named_legacy", cases=[],
                                    stage_type=None, started_at=None, ended_at=None, status="unknown"))
    files = {}
    usage = defaultdict(list)
    external_users = set()
    for row in facts["files"]:
        path = row["path"]
        required = set()
        for owner in row["consumers"]:
            sid = owner.get("stage_id") or owner.get("legacy_batch")
            if sid in stages:
                required.add(sid)
            if sid not in stages or owner.get("asset_id"):
                external_users.add(path)
        for sid in required:
            usage[sid].append(path)
        files[path] = dict(row, required_stages=sorted(required), sha256=None)

    issues = defaultdict(list)
    for issue in facts["issues"]:
        sid = issue.get("stage_id") or issue.get("legacy_batch")
        affected = {sid} if sid in stages else set(files.get(issue.get("path"), {}).get("required_stages", []))
        if not affected and not sid and not issue.get("path"):
            affected = set(stages)  # An unreadable asset catalog can conceal users of any candidate path.
        for sid in sorted(affected):
            issues[sid].append(issue)

    ends, running, recent = rank_stages(stages, now, policy["recent_per_branch"])
    for sid, stage in sorted(stages.items()):
        reasons = []
        if sid in running:
            reasons.append(reason("running", "阶段仍在执行，保留现场"))
        elif sid not in ends:
            reasons.append(reason("unknown_end", "阶段结束时间缺失或不可靠，待核"))
        elif (now - ends[sid]).days < policy["retention_days"]:
            reasons.append(reason("age", f"距阶段结束不足 {policy['retention_days']} 天"))
        reasons.extend(recent[sid])
        if sid in policy["protected_stages"]:
            reasons.append(reason("protected_stage", policy["protected_stages"][sid]))
        for path in usage[sid]:
            if Path(path) in protected_files:
                reasons.append(reason("protected_file", protected_files[Path(path)], path=path))
        for issue in issues[sid]:
            reasons.append({"code":"unverified", **issue})
        if stage["disposition_scope"] == "inventory_only":
            decision = "inventory_only"
            reasons.append(reason("legacy_scope", "历史批次仅作原位盘点"))
        elif sid in running:
            decision = "retain"
        elif sid not in ends or issues[sid]:
            decision = "review"
        elif reasons:
            decision = "retain"
        else:
            decision = "candidate"
            reasons.append(reason("eligible", "已过保留期，且各分支均无最近次数或人工保护要求"))
        stage.update(decision=decision, reasons=reasons, files=sorted(usage[sid]), proposed_release=[], keep_files=[])

    for path, item in files.items():
        targets = [sid for sid in item["required_stages"] if stages[sid]["decision"] == "candidate"]
        if not targets:
            continue
        source = root / path
        try:
            validate_existing_path_containment(root, source)
            source = inventory.source(source)
            with source.open("rb") as stream:
                before = os.fstat(stream.fileno())
                item["sha256"] = file_digest(stream, "sha256").hexdigest()
                after = source.stat()
                if (after.st_size != item["size"] or before.st_size != after.st_size or
                        before.st_mtime_ns != after.st_mtime_ns or not os.path.samestat(before, after)):
                    raise ValueError("size changed")
        except (ValueError, OSError):
            item["sha256"] = None
            for sid in targets:
                message = reason("unverified", "盘点至计算摘要期间原件缺失或变化，待核", path=path)
                stages[sid]["decision"] = "review"
                stages[sid]["reasons"] = [r for r in stages[sid]["reasons"] if r["code"] != "eligible"] + [message]
    for path, item in files.items():
        owners = item["required_stages"]
        allowed = (item["eligibility"] != "inventory_only" and path not in external_users
                   and all(stages[sid]["decision"] == "candidate" for sid in owners))
        for sid in owners:
            stages[sid]["proposed_release" if allowed else "keep_files"].append(path)
    return dict(schema_version="ui-test.retention-preview.v1", preview_id=uuid4().hex[:20],
                project=str(root), generated_at=now.isoformat(), archive_destination=destination, policy=policy,
                stages=stages, files=files, categories=facts["categories"], issues=facts["issues"])


def publish_preview(project, *, now=None, request_id=None):
    root = Path(project).resolve(strict=True)
    if request_id is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}:[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", request_id):
        raise ValueError("E_PREVIEW_REQUEST_ID: 应使用命名空间和请求标识")
    folder = root / "治理" / "清单"
    lock, history = folder.parent / ".preview.lock", folder.parent / "previews.html"
    for target in (lock, history, folder):
        validate_existing_path_containment(root, target)
    with exclusive_file_lock(lock):
        identity = sha256(request_id.encode()).hexdigest()[:20] if request_id else uuid4().hex[:20]
        page = checked_path(folder / (identity + ".html"), extra_units=16)
        record = page.with_suffix(".json")
        for target in (record, page):
            validate_existing_path_containment(root, target)
        if record.exists() or page.exists():
            saved = load_strict_json(record) if record.exists() else {}
            if (not request_id or saved.get("request_id") != request_id or saved.get("project") != str(root)
                    or saved.get("preview_id") != identity):
                raise FileExistsError("E_PREVIEW_IDENTITY_CONFLICT")
            if page.exists() and sha256(page.read_bytes()).hexdigest() != saved.get("html_sha256"):
                raise ValueError("E_PREVIEW_PUBLISHED_CONFLICT")
        if not page.exists():  # JSON alone means publication was interrupted and can be retried.
            data = build_preview(root, now=now)
            data.update(preview_id=identity, request_id=request_id)
            body = preview_html(data).encode("utf8")
            data["html_sha256"] = sha256(body).hexdigest()
            replace(record, encoded(data))
            replace(page, body)
        replace(history, history_html(root, folder).encode("utf8"))
    refresh_navigation(root)
    return page
