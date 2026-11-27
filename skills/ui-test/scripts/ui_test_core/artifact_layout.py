"""Project-owned paths for new case releases, stage runs and transient outputs."""
import json
import hashlib
import os
from pathlib import Path

from .path_planner import validate_existing_path_containment
from .path_utils import canonical_display_path, short_id
from .file_lock import exclusive_file_lock


def dispatch_task_ref(task):
    """Preserve the dispatch request's existing identity across controller and children."""
    canonical = json.dumps(os.path.normcase(str(task)), ensure_ascii=False).encode("utf8")
    return "CODEX-" + hashlib.sha256(canonical).hexdigest()


def batch_stage_id(task_ref, batch_ref):
    return "PB-" + short_id(task_ref, batch_ref)


def checked_path(path, *, extra_units=0):
    path = canonical_display_path(path)
    if len(str(path).encode("utf-16-le")) // 2 + extra_units > 220:
        raise ValueError("E_ARTIFACT_PATH_BUDGET")
    return path


class ProjectLayout:
    def __init__(self, root):
        self.root = canonical_display_path(root)

    def _path(self, category, leaf, reserve):
        path = checked_path(self.root / category / leaf, extra_units=reserve)
        validate_existing_path_containment(self.root, path)
        return path

    def case_dir(self, case_id, branch_id):
        return self._path("用例", "c" + short_id(case_id, branch_id), 52)

    def run_dir(self, stage, run_id):
        prefix = {"midscene": "m", "playwright": "p"}[stage]
        return self._path("运行", prefix + short_id(run_id), 55)

    def reserve_run(self, stage, run_id, *, exclusive=False):
        """Claim the project-wide ID before UI actions, across both stage types."""
        folder = self.run_dir(stage, run_id)
        other = self.run_dir("playwright" if stage == "midscene" else "midscene", run_id)
        guard = folder.parent / ".stage-allocation.lock"
        validate_existing_path_containment(self.root, guard)
        with exclusive_file_lock(guard):
            if other.exists():
                raise ValueError("E_CATALOG_STAGE_ID_COLLISION")
            folder.mkdir(exist_ok=not exclusive)
        return folder

    def temp_dir(self, operation_id):
        return self._path("临时", "t" + short_id(operation_id), 50)

    def related_file(self, owner, kind, identity):
        if kind not in {"修复", "恢复", "交接"}:
            raise ValueError("E_ARTIFACT_KIND")
        target = checked_path(owner / kind / (short_id(identity) + ".json"), extra_units=12)
        validate_existing_path_containment(self.root, target)
        return target

    def link_related(self, owner, kind, identity, source):
        from .codex_dispatch_state import publish
        source = canonical_display_path(source)
        validate_existing_path_containment(self.root, source)
        if not source.is_file():
            raise ValueError("E_ARTIFACT_RELATED_SOURCE")
        target = self.related_file(owner, kind, identity)
        target.parent.mkdir(parents=True, exist_ok=True)
        publish(target, {"id": identity, "source": Path(os.path.relpath(source, target.parent)).as_posix()})
        return target

    def attempt_dir(self, stage_id, run_id):
        return checked_path(self.run_dir("playwright", stage_id) / ("a" + short_id(run_id)), extra_units=118)

    def formal_attempt(self, session_id, run_id):
        dispatch = json.loads(os.environ.get("UI_TEST_CODEX_REQUEST", "{}"))
        stage = batch_stage_id(dispatch["task_ref"], dispatch["batch_ref"]) if dispatch.get("batch_ref") else session_id
        return self.attempt_dir(stage, run_id)

    def find_attempt(self, run_id):
        if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError("E_ARTIFACT_IDENTITY")
        candidates = list((self.root / "运行").glob("p*/a" + short_id(run_id)))
        legacy = self.root / "runs" / run_id
        if legacy.is_dir():
            candidates.append(legacy)
        for folder in (self.root / "cases").glob("*/runs"):
            if (folder / run_id).is_dir():
                candidates.append(folder / run_id)
        if len(candidates) != 1:
            raise ValueError("E_ARTIFACT_ATTEMPT_AMBIGUOUS_OR_MISSING")
        validate_existing_path_containment(self.root, candidates[0])
        return candidates[0]

    @classmethod
    def from_evidence(cls, source):
        for parent in canonical_display_path(source).parents:
            if (parent / "ui-test.project.yaml").is_file():
                return cls(parent)
        return None

    def register_case(self, case_id, branch_id, display_name):
        from .codex_dispatch_state import publish
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("E_ARTIFACT_DISPLAY_NAME")
        directory = self.case_dir(case_id, branch_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "case.json"
        validate_existing_path_containment(self.root, target)
        record = dict(case_id=case_id, branch_id=branch_id, display_name=display_name)
        if target.exists():
            old = json.loads(target.read_text("utf8"))
            if (old["case_id"], old["branch_id"]) != (case_id, branch_id):
                raise ValueError("E_ARTIFACT_ID_COLLISION")
            if old == record:
                return directory
        publish(target, record)
        return directory
