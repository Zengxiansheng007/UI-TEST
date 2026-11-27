"""Release only reverified, approved project paths with a durable per-file journal."""
import hashlib
import os
from pathlib import Path

from .artifact_inventory import ProjectInventory, LEGACY_CONFIG
from ui_test_core.asset_revision import digest, encoded, replace
from ui_test_core.file_lock import exclusive_file_lock
from .retention_preview import build_preview
from .stage_archive import archive_root, identity, load_approval, local_file, stage_directory, stage_signature
from .archive_reader import verify_archive
from ui_test_core.strict_json import load_strict_json


def release_inputs(root):
    """Detect changed or newly declared users, plans, protection or stage inputs during deletion."""
    inventory = ProjectInventory(root)
    inventory.scan()
    if inventory.issues:
        raise ValueError("E_RELEASE_SCAN: " + str(inventory.issues))
    paths = {path for path in inventory.files if path.suffix.lower() in {".json",".htm",".html"}}
    for ref in ("governance-settings.json", LEGACY_CONFIG, "current-cases.json", "reuse-project.json", ".reuse-state/current.json"):
        path = local_file(root, ref)
        if path.is_file():
            paths.add(path)
    stamps = {}
    for path in paths:
        stat = path.stat()
        stamps[path.relative_to(root).as_posix()] = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    return stamps


def checked_manifest(root, destination, preview, sid, archived):
    folder = stage_directory(root,destination,sid,stage_signature(preview,sid))
    if archived.get("status") != "verified" or Path(archived.get("archive_dir","")) != folder:
        raise ValueError("E_RELEASE_ARCHIVE_LOCATION")
    manifest_path = local_file(folder,"manifest.json")
    if digest(manifest_path.read_bytes()) != archived.get("manifest_sha256"):
        raise ValueError("E_RELEASE_MANIFEST_DIGEST")
    manifest = verify_archive(folder)
    stage = preview["stages"][sid]
    if (manifest["project"] != str(root) or manifest["stage"]["stage_id"] != sid or
            manifest["stage_signature"] != stage_signature(preview,sid) or set(manifest["files"]) != set(stage["files"])):
        raise ValueError("E_RELEASE_ARCHIVE_STAGE")
    for ref,row in manifest["files"].items():
        if any(row[key] != preview["files"][ref][key] for key in ("size","sha256","consumers")):
            raise ValueError("E_RELEASE_ARCHIVE_FILE " + ref)
    return manifest


def unlink_work_file(root, ref, fact):
    path = local_file(root,ref)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size != fact["size"] or hashlib.file_digest(stream,"sha256").hexdigest() != fact["sha256"]:
            raise ValueError("E_RELEASE_SOURCE_CHANGED " + ref)
    after = local_file(root,ref).stat()
    if not os.path.samestat(before,after) or before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
        raise ValueError("E_RELEASE_SOURCE_CHANGED " + ref)
    path.unlink()


def finish_release(root, receipt, result):
    if any(row["status"] == "released" for row in result["stages"].values()):
        from .archive_history import remember_release
        from ui_test_core.run_catalog import refresh_catalog
        remember_release(root, receipt)
        refresh_catalog(root)
    return receipt


def resume_files(root, approval, preview, archived, previous, manifests):
    """Recover a committed removal or an interrupted intent only inside its original verified scope."""
    journal = previous.get("journal",{})
    if previous and any(previous.get(k)!=approval[k] for k in ("approval_id","preview_id","project")):
        raise ValueError("E_RELEASE_JOURNAL_IDENTITY")
    sources, conflicts = {}, {}
    for ref, entry in journal.items():
        fact = preview["files"].get(ref,{})
        owners = fact.get("required_stages",[])
        if (not owners or owners != entry.get("stage_ids") or entry.get("status") not in {"releasing","released","blocked"} or
                any(entry.get(k)!=fact.get(k) for k in ("size","sha256")) or
                any(ref not in approval["release_paths"].get(sid,[]) or
                    ref not in archived["stages"][sid]["release_paths"] for sid in owners)):
            raise ValueError("E_RELEASE_JOURNAL_SCOPE " + ref)
        path = local_file(root,ref)
        if path.exists():
            if entry["status"]=="released":
                for sid in owners:
                    conflicts.setdefault(sid,[]).append(dict(path=ref,reason="已释放路径出现新的工作副本，保留原位"))
            continue
        if entry["status"]=="blocked":
            continue  # No successful deletion or pending intent can explain the missing file.
        for sid in owners:
            if sid in manifests:
                packed = manifests[sid]["files"][ref]["archived_ref"]
                sources[path] = local_file(Path(archived["stages"][sid]["archive_dir"]),packed)
                entry["status"] = "released"  # Earlier unlink succeeded before its completion write.
                break
    return sources, conflicts


def release(project, approval_id):
    root = Path(project).resolve(strict=True)
    batch = "治理/归档/" + identity(approval_id)
    receipt = local_file(root,batch+"/release.json")
    with exclusive_file_lock(local_file(root,"治理/.release.lock")), exclusive_file_lock(local_file(root,batch+"/batch.lock")):
        approval, preview = load_approval(root,approval_id)
        archived = load_strict_json(local_file(root,batch+"/result.json"))
        if (archived.get("complete") is not True or archived.get("approval_id") != approval_id or
                archived.get("preview_id") != approval["preview_id"] or archived.get("project") != str(root)):
            raise ValueError("E_RELEASE_ARCHIVE_RECEIPT")
        previous = load_strict_json(receipt) if receipt.exists() else {}
        if (previous.get("complete") and set(previous["stages"])==set(approval["stage_ids"]) and
                all(row["status"]=="released" for row in previous["stages"].values())):
            return finish_release(root, receipt, previous)
        destination = archive_root(root,approval["archive_destination"])
        stamps = release_inputs(root)
        states, eligible, manifests = {}, set(), {}
        for sid in approval["stage_ids"]:
            stage = preview["stages"][sid]
            item = archived["stages"].get(sid,{})
            snapshot = {k: stage[k] for k in ("stage_id","stage_type","started_at","ended_at","status","cases","report_ref","source_ref")}
            snapshot["origin"] = stage.get("origin",{})
            row = states[sid] = dict(stage=snapshot,status="blocked",reasons=[],released_paths=[],kept_paths=list(stage["files"]))
            try:
                if item.get("status") != "verified":
                    row["reasons"] = item.get("reasons") or [dict(reason="阶段尚未完成归档核验")]
                    continue
                manifests[sid] = checked_manifest(root,destination,preview,sid,item)
                row.update(archive_dir=item["archive_dir"],manifest_sha256=item["manifest_sha256"])
            except (OSError,ValueError,KeyError,TypeError) as error:
                if previous.get("stages",{}).get(sid,{}).get("manifest_sha256")==item.get("manifest_sha256") and item.get("archive_dir"):
                    row.update(archive_dir=item["archive_dir"],manifest_sha256=item["manifest_sha256"])
                row["reasons"].append(dict(reason=str(error)))
        sources, conflicts = resume_files(root,approval,preview,archived,previous,manifests)
        current = build_preview(root,archived_files=sources)
        journal = previous.get("journal",{})
        for ref, entry in journal.items():
            if entry["status"]=="released":
                for sid in entry["stage_ids"]:
                    states[sid]["released_paths"].append(ref)
                    states[sid]["kept_paths"].remove(ref)
        for sid in manifests:
            row = states[sid]
            observed = current["stages"].get(sid,{})
            try:
                if sid in conflicts:
                    row["reasons"] = conflicts[sid]
                    continue
                if current["archive_destination"] != approval["archive_destination"]:
                    raise ValueError("E_RELEASE_DESTINATION_CHANGED")
                if observed.get("decision") != "candidate":
                    row["reasons"] = observed.get("reasons") or [dict(reason="阶段缺失或已不可核实")]
                    continue
                if stage_signature(current,sid) != stage_signature(preview,sid):
                    raise ValueError("E_RELEASE_STAGE_CHANGED: 内容、引用或使用方已变更，请重新预演选择")
                unknown = [issue for issue in current["issues"] if not issue.get("stage_id") and not issue.get("legacy_batch")
                           and not issue.get("asset_id") and not current["files"].get(issue.get("path"),{}).get("required_stages")]
                if unknown:
                    row["reasons"] = unknown
                    continue
                row["status"] = "verified"
                eligible.add(sid)
            except (OSError,ValueError,KeyError,TypeError) as error:
                row["reasons"].append(dict(reason=str(error)))
        work = {}
        for sid in sorted(eligible):
            proposed = set(current["stages"][sid]["proposed_release"])
            authorized = set(approval["release_paths"][sid]) & set(archived["stages"][sid]["release_paths"])
            for ref in sorted(proposed & authorized):
                if journal.get(ref,{}).get("status")=="released":
                    continue  # Never remove a path twice or delete a subsequently recreated working file.
                owners = current["files"][ref]["required_stages"]
                if owners and all(owner in eligible and ref in approval["release_paths"][owner] and
                                  ref in archived["stages"][owner]["release_paths"] for owner in owners):
                    work[ref] = owners
        result = dict(schema_version="ui-test.stage-release.v1",project=str(root),approval_id=approval_id,
                      preview_id=approval["preview_id"],complete=False,stages=states,journal=journal)
        replace(receipt,encoded(result))  # The verified locations are durable before the first removal.
        for ref,owners in sorted(work.items()):
            if not eligible.issuperset(owners):
                continue
            try:
                if release_inputs(root) != stamps:
                    raise ValueError("E_RELEASE_REFERENCES_CHANGED: 处置期间使用方或保护状态已变化")
                fact = preview["files"][ref]
                for owner in owners:
                    folder = Path(states[owner]["archive_dir"])
                    if digest(local_file(folder,"manifest.json").read_bytes()) != states[owner]["manifest_sha256"]:
                        raise ValueError("E_RELEASE_MANIFEST_DIGEST")
                    packed = local_file(folder,manifests[owner]["files"][ref]["archived_ref"])
                    with packed.open("rb") as stream:
                        if os.fstat(stream.fileno()).st_size != fact["size"] or hashlib.file_digest(stream,"sha256").hexdigest() != fact["sha256"]:
                            raise ValueError("E_RELEASE_ARCHIVED_FILE_CHANGED " + ref)
                entry = result["journal"][ref] = dict(status="releasing",stage_ids=owners,sha256=fact["sha256"],size=fact["size"])
                replace(receipt,encoded(result))  # Intent is recoverable even if power fails immediately after unlink.
                unlink_work_file(root,ref,fact)
                stamps.pop(ref,None)
                entry["status"] = "released"
                for owner in owners:
                    states[owner]["released_paths"].append(ref)
                    states[owner]["kept_paths"].remove(ref)
            except (OSError,ValueError) as error:
                for owner in owners:
                    states[owner]["status"] = "blocked"
                    states[owner]["reasons"].append(dict(path=ref,reason=str(error)))
                    eligible.discard(owner)
                if ref in result["journal"]:
                    result["journal"][ref]["status"] = "blocked"
            replace(receipt,encoded(result))
        for sid in eligible:
            states[sid]["status"] = "released"
        result["complete"] = True
        replace(receipt,encoded(result))
    return finish_release(root, receipt, result)
