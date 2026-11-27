"""Bind one approval to a preview, then copy and verify complete stage packages."""
import hashlib
import os
import re
from pathlib import Path

from .archive_reader import archive_view, verify_archive
from ui_test_core.artifact_layout import checked_path
from ui_test_core.asset_revision import digest, encoded, replace
from ui_test_core.file_lock import exclusive_file_lock
from ui_test_core.path_planner import validate_existing_path_containment
from .retention_preview import build_preview
from ui_test_core.strict_json import load_strict_json, loads_strict


def local_file(root, relative):
    path = Path(relative)
    if path.anchor or ".." in path.parts or not path.parts:
        raise ValueError("E_ARCHIVE_LOCAL_REF")
    target = root / path
    validate_existing_path_containment(Path(root.anchor), target)  # Includes newly selected archive roots and their parents.
    return target


def archive_root(project, value):
    target = Path(value or "")
    if not target.is_absolute() or target.as_posix().startswith("//") or ".." in target.parts or target.is_relative_to(project):
        raise ValueError("E_ARCHIVE_DESTINATION: 请指定项目外的本地归档目录")
    return target


def identity(value):
    if not isinstance(value, str) or not re.fullmatch("[a-f0-9]{20}", value):
        raise ValueError("E_ARCHIVE_ID")
    return value


def stage_directory(root, destination, sid, signature):
    project_dir = local_file(destination, "p" + digest(str(root).encode())[:12])
    legacy = local_file(project_dir,"s" + digest(sid.encode())[:16])
    claim = local_file(legacy,"claim.json")
    if claim.is_file():
        old = load_strict_json(claim)
        if old.get("project") != str(root) or old.get("stage_id") != sid:
            raise ValueError("E_ARCHIVE_STAGE_CONFLICT")
        if old.get("stage_signature") == signature:
            return checked_path(legacy,extra_units=42)  # Existing receipts and interrupted copies remain valid.
    key = "v" + digest(encoded([sid,signature]))[:16]
    return checked_path(local_file(project_dir,key),extra_units=42)


def read_preview(root, preview_id):
    path = local_file(root, "治理/清单/" + identity(preview_id) + ".json")
    raw = path.read_bytes()
    preview = loads_strict(raw.decode("utf8"))
    html = local_file(root, path.with_suffix(".html").relative_to(root))
    if (preview.get("schema_version") != "ui-test.retention-preview.v1" or preview.get("project") != str(root)
            or preview.get("preview_id") != preview_id or digest(html.read_bytes()) != preview.get("html_sha256")):
        raise ValueError("E_ARCHIVE_PREVIEW_IDENTITY")
    return preview, digest(raw)


def approval_scope(root, preview, sha, stages):
    selected = sorted(set(stages))
    if not selected or any(preview["stages"].get(sid, {}).get("decision") != "candidate" for sid in selected):
        raise ValueError("E_ARCHIVE_STAGE_SELECTION: 仅可批准清单中的候选阶段")
    selected_set = set(selected)
    release = {sid: [ref for ref in preview["stages"][sid]["proposed_release"]
                     if selected_set.issuperset(preview["files"][ref]["required_stages"])] for sid in selected}
    return dict(schema_version="ui-test.archive-approval.v1",project=str(root),preview_id=preview["preview_id"],
                 preview_sha256=sha,stage_ids=selected,archive_destination=str(archive_root(root,preview["archive_destination"])),
                 release_paths=release)


def approve(project, preview_id, stages):
    root = Path(project).resolve(strict=True)
    preview, sha = read_preview(root, preview_id)
    scope = approval_scope(root, preview, sha, stages)
    aid = digest(encoded(scope))[:20]
    path = local_file(root, "治理/批准/" + aid + ".json")
    with exclusive_file_lock(local_file(root,"治理/.approval.lock")):
        if path.exists() and load_strict_json(path) != dict(approval_id=aid, **scope):
            raise ValueError("E_ARCHIVE_APPROVAL_COLLISION")
        if not path.exists():
            replace(path, encoded(dict(approval_id=aid, **scope)))
    return path


def load_approval(project, approval_id):
    root = Path(project).resolve(strict=True)
    path = local_file(root, "治理/批准/" + identity(approval_id) + ".json")
    if not path.is_file():
        raise ValueError("E_ARCHIVE_APPROVAL_MISSING: " + approval_id)
    approval = load_strict_json(path)
    scope = {key:value for key,value in approval.items() if key != "approval_id"}
    if (approval["approval_id"] != approval_id or digest(encoded(scope))[:20] != approval_id
            or approval["project"] != str(root)):
        raise ValueError("E_ARCHIVE_APPROVAL_IDENTITY")
    preview, sha = read_preview(root, approval["preview_id"])
    if sha != approval["preview_sha256"]:
        raise ValueError("E_ARCHIVE_PREVIEW_CHANGED")
    if approval_scope(root, preview, sha, approval["stage_ids"]) != scope:
        raise ValueError("E_ARCHIVE_APPROVAL_SCOPE")
    return approval, preview


def stage_signature(preview, sid):
    stage = preview["stages"][sid]
    facts = {k:v for k,v in stage.items() if k not in {"decision","reasons","proposed_release","keep_files"}}
    return digest(encoded(dict(stage=facts,files={ref:preview["files"][ref] for ref in stage["files"]})))


def copy_object(source, target, row):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        with target.open("rb") as stream:
            if target.stat().st_size == row["size"] and hashlib.file_digest(stream, "sha256").hexdigest() == row["sha256"]:
                return
        raise ValueError("E_ARCHIVE_OBJECT_CONFLICT " + row["path"])
    temp = local_file(target.parent,"t"+target.stem[:23])  # Shorter than the finished object's budgeted path.
    with temp.open("wb") as output:  # The stage lock owns this one resumable workspace, including after a hard stop.
        try:
            checksum, size = hashlib.sha256(), 0
            with source.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    output.write(block)
                    checksum.update(block)
                    size += len(block)
            if size != row["size"] or checksum.hexdigest() != row["sha256"]:
                raise ValueError("E_ARCHIVE_SOURCE_CHANGED " + row["path"])
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            output.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def copy_stage(root, folder, approval, preview, sid, checkpoint):
    stage = preview["stages"][sid]
    claim = dict(project=str(root),stage_id=sid,stage_signature=stage_signature(preview,sid))
    claim_path = local_file(folder, "claim.json")
    if claim_path.exists():
        if load_strict_json(claim_path) != claim:
            raise ValueError("E_ARCHIVE_STAGE_CONFLICT")
    elif folder.exists() and any(folder.iterdir()):
        raise ValueError("E_ARCHIVE_EXISTING_DIRECTORY")
    else:
        replace(claim_path, encoded(claim))
    manifest_path = local_file(folder, "manifest.json")
    if manifest_path.exists():
        checkpoint("verifying",None)
        manifest = verify_archive(folder)
        if manifest["stage_signature"] != claim["stage_signature"]:
            raise ValueError("E_ARCHIVE_STAGE_CONFLICT")
        return
    files = {}
    for ref in stage["files"]:
        row = preview["files"][ref]
        suffix = Path(ref).suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            suffix = ".bin"
        packed = "objects/" + digest(ref.encode())[:24] + suffix
        if not row["sha256"]:
            raise ValueError("E_ARCHIVE_FILE_DIGEST " + ref)
        copy_object(local_file(root, ref),checked_path(local_file(folder, packed)),row)
        files[ref] = dict(original_ref=ref,archived_ref=packed,size=row["size"],sha256=row["sha256"],
                          category=row["category"],consumers=row["consumers"])
        checkpoint("copying",ref)
    settings = local_file(root, "governance-settings.json")
    original = load_strict_json(settings).get("original_project_root") if settings.exists() else None
    manifest = dict(schema_version="ui-test.stage-archive.v1",project=str(root),original_project_root=original,
                    stage_signature=claim["stage_signature"],approval_id=approval["approval_id"],preview_id=preview["preview_id"],
                    stage=stage,report_ref=stage.get("report_ref"),source_ref=stage.get("source_ref"),files=files,
                    downstream=sorted(ref for ref,fact in preview["stages"].items() if fact.get("origin",{}).get("stage_id") == sid))
    # The reader verifies the copied stage facts and links using only the archive directory.
    checkpoint("verifying",None)
    body, checks, related = archive_view(folder, manifest)
    manifest.update(verification=checks,reader_sha256=digest(body))
    replace(local_file(folder, "index.html"), body)
    if related is not None:
        manifest["related_sha256"] = digest(related)
        replace(local_file(folder,"related.html"),related)
    replace(manifest_path, encoded(manifest))
    verify_archive(folder)


def archive(project, approval_id):
    root = Path(project).resolve(strict=True)
    approval, preview = load_approval(root, approval_id)
    destination = archive_root(root, approval["archive_destination"])
    result_path = local_file(root, "治理/归档/" + approval_id + "/result.json")
    lock = local_file(root, "治理/归档/" + approval_id + "/batch.lock")
    result = dict(approval_id=approval_id,preview_id=approval["preview_id"],project=str(root),stages={},complete=False)
    with exclusive_file_lock(lock):
        release_record = local_file(root,"治理/归档/" + approval_id + "/release.json")
        released = load_strict_json(release_record) if release_record.exists() else {}
        previous, existing, unavailable, sources = {}, {}, {}, {}
        progress_path = result_path
        if released.get("journal"):
            from .stage_release import checked_manifest, resume_files
            previous = load_strict_json(result_path)
            if (previous.get("approval_id")!=approval_id or previous.get("project")!=str(root) or
                    previous.get("preview_id")!=approval["preview_id"] or previous.get("complete") is not True):
                raise ValueError("E_RELEASE_ARCHIVE_RECEIPT")
            for sid,prior in previous["stages"].items():
                if prior.get("manifest_sha256"):
                    try:
                        existing[sid] = checked_manifest(root,destination,preview,sid,dict(prior,status="verified"))
                    except (OSError,ValueError,KeyError,TypeError) as error:
                        unavailable[sid] = str(error)
            sources,_ = resume_files(root,approval,preview,previous,released,existing)
            # Keep the previous complete release input durable while any remaining stage is being copied.
            progress_path = local_file(result_path.parent,"copy-progress.json")
        current = build_preview(root,archived_files=sources)
        for sid in approval["stage_ids"]:
            if sid in existing or sid in unavailable:
                row = dict(previous["stages"][sid])
                observed = current["stages"].get(sid,{})
                if sid in unavailable:
                    row.update(status="blocked",reasons=[dict(reason=unavailable[sid])])
                elif current["archive_destination"] != approval["archive_destination"]:
                    row.update(status="blocked",reasons=[dict(reason="归档目的地已变更")])
                elif observed.get("decision") != "candidate":
                    row.update(status="blocked",reasons=observed.get("reasons") or [dict(reason="阶段缺失或已不可核实")])
                elif stage_signature(current,sid) != stage_signature(preview,sid):
                    row.update(status="blocked",reasons=[dict(reason="阶段内容、引用或使用方已变化")])
                else:
                    row.update(status="verified",reasons=[])
                result["stages"][sid] = row
                replace(progress_path,encoded(result))
                continue
            row = dict(status="blocked",release_paths=[],reasons=[])
            result["stages"][sid] = row
            observed = current["stages"].get(sid, {})
            if current["archive_destination"] != approval["archive_destination"]:
                row["reasons"].append(dict(reason="归档目的地已变更"))
            elif observed.get("decision") != "candidate":
                row["reasons"].extend(observed.get("reasons") or [dict(reason="阶段缺失或已不可核实")])
            elif stage_signature(current, sid) != stage_signature(preview, sid):
                row["reasons"].append(dict(reason="阶段内容、引用、使用方或可释放范围已变化"))
            else:
                try:
                    folder = stage_directory(root, destination, sid, stage_signature(preview,sid))
                    if folder.is_relative_to(root) or root.is_relative_to(folder):
                        raise ValueError("E_ARCHIVE_DESTINATION")
                    row.update(status="copying",archive_dir=str(folder),copied_paths=[])
                    def checkpoint(status, ref):
                        row["status"] = status
                        if ref is not None:
                            row["copied_paths"].append(ref)
                        replace(progress_path,encoded(result))
                    checkpoint("copying",None)
                    with exclusive_file_lock(local_file(folder.parent, folder.name + ".lock")):
                        copy_stage(root, folder, approval, preview, sid, checkpoint)
                    row["copied_paths"] = list(preview["stages"][sid]["files"])
                    row.update(status="verified",archive_dir=str(folder),manifest_sha256=digest((folder/"manifest.json").read_bytes()))
                except (OSError, ValueError, TypeError, KeyError) as error:
                    row["status"] = "blocked"
                    row["reasons"].append(dict(reason=str(error)))
            replace(progress_path, encoded(result))  # Record each stage before proceeding to the next.
        verified = {sid for sid,row in result["stages"].items() if row["status"]=="verified"}
        for sid in verified:
            allowed = set(current["stages"].get(sid,{}).get("proposed_release",[]))
            eligible = [
                path for path in approval["release_paths"][sid] if path in allowed
                and verified.issuperset(current["files"][path]["required_stages"])]
            # Old removals remain accountable when protection or media availability changes between retries.
            logged = {ref for ref,entry in released.get("journal",{}).items() if sid in entry["stage_ids"]}
            result["stages"][sid]["release_paths"] = sorted(set(eligible)|logged)
        result["complete"] = True
        replace(result_path, encoded(result))
        if progress_path != result_path:
            replace(progress_path,encoded(result))
    return result_path
