"""Rebuild released-run history from compact receipts and restore verified stage copies."""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from shutil import copyfile
from tempfile import TemporaryDirectory

from .archive_reader import ArchiveFiles, verify_archive
from ui_test_core.artifact_layout import checked_path
from ui_test_core.asset_revision import digest, encoded, replace
from ui_test_core.file_lock import exclusive_file_lock
from .stage_archive import archive_root, identity, local_file
from ui_test_core.strict_json import load_strict_json


def receipt_path(root, checksum, category="历史"):
    if not isinstance(checksum, str) or not re.fullmatch("[a-f0-9]{64}", checksum):
        raise ValueError("E_HISTORY_MANIFEST_ID")
    return local_file(root, f"治理/{category}/{checksum}.json")


def remember_release(root, path):
    """The release journal provides enough facts even when an old archive is unplugged."""
    release = load_strict_json(path)
    aid = identity(release["approval_id"])
    if (path != local_file(root, f"治理/归档/{aid}/release.json") or release["project"] != str(root)
            or release.get("schema_version") != "ui-test.stage-release.v1"):
        raise ValueError("E_HISTORY_RELEASE_IDENTITY")
    if not release["complete"]:
        return
    for sid, item in release["stages"].items():
        if item["status"] != "released":
            continue
        target = receipt_path(root, item["manifest_sha256"])
        if target.exists():
            continue
        stage = item["stage"]
        if stage["stage_id"] != sid:
            raise ValueError("E_HISTORY_STAGE_IDENTITY")
        archive = archive_root(root, item["archive_dir"])
        receipt = dict(schema_version="ui-test.archive-history.v1", project=str(root), stage=stage,
                       manifest_sha256=item["manifest_sha256"], archive_dir=str(archive),
                       approval_id=aid, preview_id=identity(release["preview_id"]), disposition=item["status"],
                       recorded_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
        replace(target, encoded(receipt))


def history_records(root):
    # Lazily import releases written before compact receipts existed.
    for path in local_file(root, "治理/归档").glob("*/release.json"):
        remember_release(root, local_file(root, path.relative_to(root)))
    records = []
    for path in local_file(root, "治理/历史").glob("*.json"):
        record = load_strict_json(receipt_path(root, path.stem))
        if (record.get("schema_version") != "ui-test.archive-history.v1" or record["project"] != str(root)
                or record["manifest_sha256"] != path.stem or record["disposition"] != "released"):
            raise ValueError("E_HISTORY_RECEIPT_IDENTITY")
        records.append(record)
    return sorted(records, key=lambda r: (r["recorded_at"], r["manifest_sha256"]), reverse=True)


def readable_package(root, record, value):
    """Check the sealed manifest before exposing any external file link."""
    folder = archive_root(root, value)
    try:
        path = local_file(folder, "manifest.json")
        if not path.is_file():
            return "offline", None
        if digest(path.read_bytes()) != record["manifest_sha256"]:
            return "changed", None
        manifest = load_strict_json(path)
        if (manifest["stage"]["stage_id"] != record["stage"]["stage_id"] or manifest["project"] != str(root)
                or digest(local_file(folder, "index.html").read_bytes()) != manifest["reader_sha256"]):
            return "changed", None
        source = manifest["files"][manifest["source_ref"]]
        if digest(local_file(folder, source["archived_ref"]).read_bytes()) != source["sha256"]:
            return "changed", None
        return "online", manifest
    except FileNotFoundError:
        return "offline", None
    except (OSError, ValueError, KeyError, TypeError):
        return "unavailable", None


def catalog_archive(root, record):
    checksum = record["manifest_sha256"]
    stage = record["stage"]
    archive = Path(record["archive_dir"])
    media, manifest = readable_package(root, record, archive)
    folder = archive if manifest is not None else None
    restored = None
    pointer = receipt_path(root, checksum, "恢复")
    if pointer.is_file():
        mapping = load_strict_json(pointer)
        if (mapping["project"] != str(root) or mapping["manifest_sha256"] != checksum
                or mapping["stage_id"] != stage["stage_id"]):
            raise ValueError("E_HISTORY_RESTORE_IDENTITY")
        restored = Path(mapping["directory"])
        _, recovered = readable_package(root, record, restored)
        if recovered is not None:
            folder, manifest = restored, recovered
    links = {}
    if manifest is not None:
        files = ArchiveFiles(folder, manifest)
        source = files.json(manifest["source_ref"])
        for case in source["cases"]:
            for attempt in case["attempts"]:
                refs = (attempt.get("execution_ref"), attempt.get("evidence_ref"), (attempt.get("binding") or {}).get("entry"))
                key = (case["case_id"], case["branch_id"], attempt["attempt_ref"])
                links[key] = tuple(str(files.path(files.row("", ref)["archived_ref"])) if ref else None for ref in refs)
    archive_row = (stage["stage_id"], checksum, str(archive), record["disposition"], media,
                   str(restored) if restored else None, str(folder/"index.html") if folder else None,
                   record["approval_id"], record["recorded_at"])
    return archive_row, links


def contains_archive_partition(directory):
    """Recognize another medium from a persisted claim in the governed package layout."""
    for partition in directory.glob("p????????????"):
        if not re.fullmatch("p[a-f0-9]{12}", partition.name):
            continue
        local_file(directory, partition.name)
        for claim in partition.glob("[sv]????????????????/claim.json"):
            if (re.fullmatch("[sv][a-f0-9]{16}", claim.parent.name) and
                    {"stage_id", "project", "stage_signature"} <= load_strict_json(local_file(directory,claim.relative_to(directory))).keys()):
                return True
    return False


def restore_target(root, records, destination, record):
    """Reserve restoration space outside all known project and archive trees."""
    destination = Path(destination).absolute()
    if not destination.is_absolute() or destination.as_posix().startswith("//") or ".." in destination.parts:
        raise ValueError("E_RESTORE_DESTINATION")
    protected = {root}
    settings_path = local_file(root, "governance-settings.json")
    settings = load_strict_json(settings_path) if settings_path.is_file() else {}
    for key in ("archive_destination", "original_project_root"):
        value = settings.get(key)
        if value and Path(value).is_absolute():
            protected.add(Path(value))
    for item in records:
        # Both supported archive formats use <medium>/<project key>/<stage key>.
        protected.add(archive_root(root, item["archive_dir"]).parent.parent)
    for path in local_file(root, "治理/批准").glob("*.json"):
        approval = load_strict_json(local_file(root,path.relative_to(root)))
        if approval.get("project") == str(root) and approval.get("archive_destination"):
            protected.add(archive_root(root,approval["archive_destination"]))
    if any(destination.is_relative_to(p) or p.is_relative_to(destination) for p in protected):
        raise ValueError("E_RESTORE_DESTINATION")
    target = checked_path(local_file(destination, "r" + record["manifest_sha256"][:16]), extra_units=49)
    for ancestor in (destination, *destination.parents):
        # Other projects and copied archives can exist outside this project's known media.
        if any((ancestor/name).is_file() for name in ("governance-settings.json", "current-cases.json", "catalog-settings.json",
                                                      "runs.sqlite3", "运行/.stage-allocation.lock", "skills/ui-test/SKILL.md")):
            raise ValueError("E_RESTORE_DESTINATION")
        if (ancestor/"objects").is_dir() and (ancestor/"manifest.json").is_file():
            if load_strict_json(ancestor/"manifest.json").get("schema_version") == "ui-test.stage-archive.v1":
                raise ValueError("E_RESTORE_DESTINATION")
        if contains_archive_partition(ancestor):
            raise ValueError("E_RESTORE_DESTINATION")
    # Existing restore roots can contain several independent stage directories.
    if target.exists() and readable_package(root, record, target)[0] != "online":
        raise ValueError("E_RESTORE_TARGET_CONFLICT")
    return target


def restore_stage(project, stage_id, destination, manifest_sha256=None):
    root = Path(project).resolve(strict=True)
    records = history_records(root)
    matches = [r for r in records if r["stage"]["stage_id"] == stage_id
               and (manifest_sha256 is None or r["manifest_sha256"] == manifest_sha256)]
    if len(matches) != 1:
        raise ValueError("E_RESTORE_STAGE_SELECTION: 请按阶段号和归档清单摘要选择一份记录")
    record = matches[0]
    source = Path(record["archive_dir"])
    checksum = record["manifest_sha256"]
    target = restore_target(root, records, destination, record)
    destination = target.parent
    with exclusive_file_lock(local_file(destination, target.name + ".lock")):
        state, manifest = readable_package(root, record, source)
        if state != "online":
            raise ValueError("E_RESTORE_MEDIA: 归档介质离线、不可读或清单已变化")
        verify_archive(source)
        if not target.exists():
            with TemporaryDirectory(prefix=".r-", dir=destination) as staging:
                incoming = Path(staging)/"package"
                incoming.mkdir()
                names = ["manifest.json", "index.html", *(row["archived_ref"] for row in manifest["files"].values())]
                if manifest.get("related_sha256"):
                    names.append("related.html")
                for name in names:
                    out = local_file(incoming, name)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    copyfile(local_file(source, name), out)
                if digest((incoming/"manifest.json").read_bytes()) != checksum:
                    raise ValueError("E_RESTORE_MANIFEST_CHANGED")
                verify_archive(incoming)
                os.rename(incoming, target)
        if readable_package(root, record, target)[0] != "online":
            raise ValueError("E_RESTORE_TARGET_CONFLICT")
        verify_archive(target)
        pointer = dict(project=str(root), stage_id=stage_id, manifest_sha256=checksum, directory=str(target))
        replace(receipt_path(root, checksum, "恢复"), encoded(pointer))
    from ui_test_core.run_catalog import refresh_catalog
    refresh_catalog(root)
    return target/"index.html"
