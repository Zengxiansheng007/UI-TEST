"""Atomic project decisions and idempotent delivery of step-use evidence."""
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .file_lock import exclusive_file_lock


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staged = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            staged.unlink(missing_ok=True)
            raise
    try:
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


class RevisionConflict(ValueError):
    """The caller must read the current decision and reassess its proposed change."""


class AssetCatalog:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.root = self.project / ".reuse-state"

    def state(self):
        pointer = self.root / "current.json"
        if not pointer.exists():
            return dict(revision=0, assets={}, pauses=[], versions={})
        expected = json.loads(pointer.read_bytes())["sha256"]
        data = (self.root / "records" / expected[:32]).read_bytes()
        if digest(data) != expected:
            raise ValueError("catalog manifest digest mismatch")
        return json.loads(data)

    def revision(self):
        return self.state()["revision"]

    def pin(self):
        from .reusable_assets import discover
        with exclusive_file_lock(self.root / "catalog.lock"):
            state = self.state()
            return state["revision"], discover(self.project, state=state)

    def _commit(self, expected_revision, mutate):
        with exclusive_file_lock(self.root / "catalog.lock"):
            state = self.state()
            if state["revision"] != expected_revision:
                raise RevisionConflict(f"expected {expected_revision}, current {state['revision']}")
            mutate(state)
            state["revision"] += 1
            data = encoded(state)
            sha = digest(data)
            record = self.root / "records" / sha[:32]
            if record.exists() and record.read_bytes() != data:
                raise ValueError("revision filename collision")
            replace(record, data)
            replace(self.root / "current.json", encoded(dict(sha256=sha)))
            return state["revision"]

    def publish(self, asset_id, descriptor, source_bytes, *, expected_revision):
        from .reusable_assets import discover, matches

        def apply(state):
            row = dict(descriptor)
            rows = discover(self.project, state=state)
            sha = digest(source_bytes)
            if row["sha256"] != sha or row["enabled"] is not True:
                raise ValueError("expected an enabled reviewed version with matching content")
            target = self.root / "objects" / sha[:32]
            row.update(recovery_source=target.relative_to(self.project).as_posix())
            row.pop("status", None)
            row.pop("declarations", None)
            versions = state["versions"].setdefault(asset_id, {})
            key = str(row["version"])
            old = rows.get(asset_id)
            if old and old["version"] == row["version"] or key in versions:
                raise ValueError("asset version already registered")
            if any(dep not in rows or rows[dep]["status"] != "available" for dep in row["dependencies"]):
                raise ValueError("missing dependency version")
            if old:
                versions.setdefault(str(old["version"]), old)
            if not target.is_file():
                replace(target, source_bytes)
            if not matches(target, row):
                raise ValueError("published symbol or recovery digest mismatch")
            versions[key] = state["assets"][asset_id] = row

        return self._commit(expected_revision, apply)

    def pause(self, asset_id, version, scope, *, expected_revision):
        from .reusable_assets import discover

        def apply(state):
            row = discover(self.project, state=state).get(asset_id)
            historical = state["versions"].get(asset_id, {})
            if not row or (row["version"] != version and str(version) not in historical):
                raise ValueError("unknown asset version")
            decision = dict(asset_id=asset_id, version=version, scope=dict(scope))
            if decision not in state["pauses"]:
                state["pauses"].append(decision)

        return self._commit(expected_revision, apply)

    def paused(self, asset_id, version, scope):
        return any(p["asset_id"] == asset_id and p["version"] == version
                   and all(k not in scope or scope[k] == v for k, v in p["scope"].items())
                   for p in self.state()["pauses"])


def deliver_event(directory, event):
    """Persist the original or conflicting payload, without replaying its action."""
    key = [event[k] for k in ("run_id", "step_id", "attempt_ref", "sequence")]
    data = encoded(event)
    root = Path(directory)
    target = root / digest(encoded(key))[:32]
    with exclusive_file_lock(root / "delivery.lock"):
        if not target.is_file():
            replace(target, data)
            return "recorded"
        if target.read_bytes() == data:
            return "duplicate"
        conflict = root / "conflicts" / digest(data)[:32]
        if conflict.exists() and conflict.read_bytes() != data:
            raise ValueError("conflict filename collision")
        if not conflict.is_file():
            replace(conflict, data)
        return "conflict"

