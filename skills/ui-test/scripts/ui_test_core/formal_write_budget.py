"""Bind reviewed formal batch limits to each protected pytest write permit."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from .strict_json import loads_strict


VERSION = "ui-test.formal-write-budget.v1"


def read_budget(path, digest, batch, task_ref):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("E_FORMAL_BUDGET_DIGEST")
    doc = loads_strict(raw.decode("utf8"))
    if not isinstance(batch, str) or not batch or not isinstance(doc, dict) or doc.get("batch") != batch or not isinstance(doc.get("nodes"), list):
        raise ValueError("E_FORMAL_BUDGET_BATCH")
    if doc.keys() != {"schema_version", "task_ref", "batch", "nodes"} or doc["schema_version"] != VERSION:
        raise ValueError("E_FORMAL_BUDGET_VERSION")
    if not task_ref or doc["task_ref"] != task_ref:
        raise ValueError("E_FORMAL_BUDGET_TASK")
    limits = {}
    for row in doc["nodes"]:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k] for k in ("node", "case_id", "branch_id")):
            raise ValueError("E_FORMAL_BUDGET_NODE")
        if row["node"] in limits:
            raise ValueError("E_FORMAL_BUDGET_DUPLICATE")
        if row.keys() != {"node", "case_id", "branch_id", "phases"}:
            raise ValueError("E_FORMAL_BUDGET_PHASE")
        phases = row["phases"]
        if not isinstance(phases, dict) or any(not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", key)
                or type(count) is not int or count not in (0, 1) for key, count in phases.items()):
            raise ValueError("E_FORMAL_BUDGET_PHASE")
        limits[row["node"]] = (row["case_id"], row["branch_id"], phases)
    return limits


@dataclass(frozen=True)
class ItemBudget:
    path: Path
    digest: str
    batch: str
    task_ref: str
    directory: Path
    run: str
    node: str
    case: str
    branch: str
    project_phases: tuple
    project_budget: dict | None

    def check(self, phase=None):
        if not self.project_phases:
            raise ValueError("E_FORMAL_BUDGET_READ_ONLY")
        row = read_budget(self.path, self.digest, self.batch, self.task_ref).get(self.node)
        if row is None or row[:2] != (self.case, self.branch):
            raise ValueError("E_FORMAL_BUDGET_NODE")
        allowed = [p for p in self.project_phases if row[2].get(p) == 1]
        if not allowed or (phase is not None and phase not in allowed):
            raise ValueError("E_FORMAL_BUDGET_PHASE")

    def reserve(self, run, case, branch, phase, session_budget):
        if session_budget != self.project_budget:
            raise ValueError("E_FORMAL_BUDGET_PROJECT_PHASES")
        if (run, case, branch) != (self.run, self.case, self.branch):
            raise ValueError("E_FORMAL_BUDGET_IDENTITY")
        self.check(phase)
        key = json.dumps([self.task_ref, self.batch, self.node, phase], ensure_ascii=False).encode("utf8")
        receipt = self.directory / (hashlib.sha256(key).hexdigest() + ".once")
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            with receipt.open("x", encoding="utf8") as stream:
                json.dump(dict(run=run, case=case, branch=branch, phase=phase, budget=self.digest), stream)
        except FileExistsError as exc:
            raise ValueError("E_FORMAL_BUDGET_EXHAUSTED") from exc
        def check_consumption():
            if active is not self:
                raise ValueError("E_FORMAL_BUDGET_IDENTITY")
            self.check(phase)
            try:
                receipt.with_suffix(".consumed").touch(exist_ok=False)
            except FileExistsError as exc:
                raise ValueError("E_FORMAL_BUDGET_CONSUMED") from exc
        return check_consumption


active = None  # pytest executes a single item per worker process.


@contextmanager
def bind_item(budget):
    global active
    previous = active
    active = budget
    try:
        yield
    finally:
        active = previous
