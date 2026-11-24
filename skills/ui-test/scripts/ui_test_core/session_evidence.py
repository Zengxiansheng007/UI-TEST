"""Reconcile local pytest reports with the immutable attempt and receipt on disk."""
import hashlib
from pathlib import Path

from .case_contracts import canonical_hash, validate_document
from .execution_attempt_store import ExecutionAttemptStore, derive_attempt_directory_name
from .finalization_transaction import FinalizationTransaction
from .path_utils import io_path
from .strict_json import load_strict_json


def _text_digest(value):
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_node_evidence(evidence_root: Path, session_id: str, node: dict) -> bool:
    """Resolve evidence by identity, never by a caller-supplied absolute path."""
    try:
        run, node_id = node["run_id"], node["node_id"]
        attempt = "attempts/" + derive_attempt_directory_name(run_id=run, node_id=node_id)
        if node.get("attempt_ref", attempt) != attempt or node["terminal_ref"] != attempt + "/terminal.json":
            return False
        root = io_path(Path(evidence_root))
        start = load_strict_json(root / attempt / "attempt-start.json")
        terminal = load_strict_json(root / node["terminal_ref"])
        if (start.get("session_id") != session_id or start["run_id_digest"] != _text_digest(run)
                or start["node_id_digest"] != _text_digest(node_id) or start["attempt_id"] != _text_digest(f"{run}:{node_id}")
                or terminal.get("session_id", session_id) != session_id
                or terminal.get("attempt_id", start["attempt_id"]) != start["attempt_id"]
                or canonical_hash(terminal) != node["terminal_hash"]
                or terminal.get("is_unique_terminal") is not True):
            return False
        status = node["finalization_status"]
        passed = terminal["status"] == "passed"
        if "disposition" in node and (node["disposition"] == "passed") != passed:
            return False
        if status.startswith("not_applicable_"):
            return passed and start["finalization_mode"] == status and not terminal.get("receipt_ref")
        if status == "missing":
            return not passed and not terminal.get("receipt_ref")
        if node["receipt_ref"] != terminal["receipt_ref"] or node["receipt_hash"] != terminal["receipt_hash"]:
            return False
        ref = node["receipt_ref"]
        if ref == attempt + "/finalization-failure-receipt.json":
            if status != "failed" or passed:
                return False
            receipt_file = root / ref
        elif ref == f"runs/{run}/finalization/finalization-receipt.json":
            store = ExecutionAttemptStore(evidence_root=evidence_root)
            target = store.session_run_target(run_id=run, node_id=node_id)
            receipt_file = io_path(target) / "finalization" / "finalization-receipt.json"
            copy = root / attempt / "session-receipt.json"
            if copy.exists() and canonical_hash(load_strict_json(copy)) != node["receipt_hash"]:
                return False
            if status == "committed":
                closure = FinalizationTransaction(target).read_committed(immutable_snapshot=True)
                if not closure:
                    return False
                result = closure["run_result"]
                identity = dict(session_id=session_id, node_id=node_id, run_id=run, attempt_ref=attempt,
                                pre_terminal_events_hash=terminal["pre_terminal_events_hash"])
                if (any(result[key] != value for key, value in identity.items())
                        or (passed and result["overall_status"] != "passed")
                        or terminal["commit_manifest_ref"] != f"runs/{run}/finalization/finalization-commit.json"
                        or canonical_hash(closure["manifest"]) != terminal["commit_manifest_hash"]):
                    return False
        else:
            return False
        receipt = load_strict_json(receipt_file)
        if validate_document(receipt, "run-finalization-receipt-v1.schema.json"):
            return False
        sealed_hash = canonical_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
        return (canonical_hash(receipt) == node["receipt_hash"]
                and receipt["receipt_hash"] == sealed_hash
                and all(receipt[k] == v for k, v in (("session_id", session_id), ("run_id", run), ("node_id", node_id)))
                and ((status == "committed" and receipt["status"] == "committed"
                      and receipt["commit_manifest_hash"] == terminal["commit_manifest_hash"]
                      and start["finalization_mode"] == "transaction-v1")
                     or (status == "failed" and not passed and receipt["status"] != "committed")))
    except (OSError, KeyError, ValueError, TypeError, AttributeError, RuntimeError):
        return False


class FormalSession:
    """One controller reconciles all deliveries, including repeated and crash reports."""
    def __init__(self):
        self.expected = []
        self.collection = None
        self.consistent = True
        self.worker_errors = []
        self.phases = {}
        self.records = {}
        self.run_ids = {}
        self.conflicts = set()
        self.not_executed = {}
        self.denied_duplicate_nodes = set()

    def observe_collection(self, all_nodes, formal):
        current = (list(all_nodes), list(formal))
        if self.collection is None:
            self.collection = current
        elif self.collection != current:
            self.consistent = False
        self.expected = list(dict.fromkeys([*self.expected, *formal]))
        if len(set(formal)) != len(formal):
            self.consistent = False

    def pytest_runtest_logreport(self, report):
        denial = getattr(report, "ui_test_not_executed", None)
        if denial:
            self.not_executed[report.nodeid] = denial
            if denial == "E_ATTEMPT_START_ALREADY_EXISTS":
                self.denied_duplicate_nodes.add(report.nodeid)
            return  # 未准入的 setup 报告不属于已执行的另一份投递。
        self.phases.setdefault(report.nodeid, []).append((report.when, report.outcome))
        run_id = getattr(report, "ui_test_run_id", None)
        if run_id and self.run_ids.setdefault(report.nodeid, run_id) != run_id:
            self.conflicts.add(report.nodeid)
        row = getattr(report, "ui_test_node", None)
        if row is not None:
            previous = self.records.setdefault(report.nodeid, row)
            if previous != row or row["node_id"] != report.nodeid:
                self.conflicts.add(report.nodeid)

    def reconcile(self, root, session_id):
        rows = []
        for node_id in self.expected:
            phases = self.phases.get(node_id, [])
            row = self.records.get(node_id)
            outcomes = {outcome for _, outcome in phases}
            if node_id in self.conflicts:
                reason = "conflicting-deliveries"
            elif row is not None and not verify_node_evidence(root, session_id, row):
                reason = "invalid-terminal-or-receipt"
            elif row is not None:
                public = {k: v for k, v in row.items() if not k.startswith("_")}
                if "skipped" in outcomes and public["disposition"] != "passed":
                    public["disposition"] = "skipped"
                passed_phases = {("setup", "passed"), ("call", "passed"), ("teardown", "passed")}
                if public["disposition"] != "passed" or set(phases) == passed_phases:
                    rows.append(public)
                    continue
                reason = "phase-report-mismatch"
            else:
                reason = "no-terminal-record" if phases else "not-dispatched"
            disposition = "unknown" if phases else "not_executed"
            if "skipped" in outcomes:
                disposition = "skipped"
            elif "failed" in outcomes and all(phase in ("setup","call","teardown") for phase, _ in phases):
                disposition = "failed"
            # A refused delivery can also target a previous session's already completed run.
            # xdist reports the current node's hard crash with an unclassified phase before setup can return.
            owner_observed = node_id in self.run_ids or any(phase == "???" and outcome == "failed" for phase, outcome in phases)
            if row is None and node_id in self.denied_duplicate_nodes and owner_observed:
                disposition, reason = "unknown", "no-terminal-record"
            elif row is None and node_id in self.not_executed and node_id not in self.run_ids:
                disposition, reason = "not_executed", self.not_executed[node_id]
            missing = dict(node_id=node_id, disposition=disposition, finalization_status="missing", missing_reason=reason)
            if node_id in self.run_ids:
                missing["run_id"] = self.run_ids[node_id]
                directory = derive_attempt_directory_name(run_id=missing["run_id"], node_id=node_id)
                missing["attempt_ref"] = "attempts/" + directory
            rows.append(missing)
        return rows
