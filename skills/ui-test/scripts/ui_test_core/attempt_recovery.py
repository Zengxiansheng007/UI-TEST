"""Inspect unfinished attempts and recover one identified execution under its OS lock."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .execution_attempt_store import ExecutionAttemptStore, derive_attempt_directory_name
from .file_lock import FileLockBusy
from .finalization_store import FinalizationStore, FinalizationStoreError


class AttemptRecovery:
    def __init__(self, *, store: ExecutionAttemptStore, now_func=None, pid_func=None,
                 host_func=None, is_alive_func=None) -> None:
        self._store = store  # Legacy constructor parameters remain accepted by historical callers.

    def scan_and_recover(self, *, finalization_probe=None) -> dict:
        """Compatibility inventory. Only an explicitly named attempt can be changed."""
        unfinished = self._store.scan_unfinished_attempts()
        return {"recovered_attempts": [], "unresolved_attempts": unfinished,
                "warnings": [f"previous-attempt-unknown:{row['attempt_dir']}" for row in unfinished],
                "total_scanned": len(unfinished)}

    def recover_with_pid_check(self, *, run_id, node_id, recorded_pid, recorded_host) -> dict:
        """Historical PID-only calls cannot establish ownership or identify a transaction."""
        return {"run_id": run_id, "node_id": node_id, "recovery_type": "unresolved"}

    def recover_attempt(self, *, run_id: str, node_id: str, run_root: str | Path) -> dict:
        """Inspect the exact run's transaction and append at most one recovery event."""
        identity = dict(run_id=run_id, node_id=node_id)
        try:
            with self._store.attempt_ownership(**identity, recovery=True):
                start = self._store.read_attempt_start(**identity)
                if not start or any(
                    start.get(key + "_digest") != "sha256:" + hashlib.sha256(value.encode()).hexdigest()
                    for key, value in identity.items()
                ):
                    return {"recovery_type": "unknown-owner"}
                if not self._store.matches_run_target(**identity, run_root=run_root):
                    return {"recovery_type": "unknown-owner"}  # Unbound or unrelated transaction directories are read-only.
                terminal = self._store.read_terminal(**identity)
                if terminal is not None:
                    return {"recovery_type": "terminal"}
                transaction = FinalizationStore(run_root)
                commit = transaction.read_commit()
                receipt = transaction.read_receipt()
                for document in (commit, receipt):
                    if document is not None and any(document.get(k) != v for k, v in {
                        **identity, "session_id": start["session_id"]
                    }.items()):
                        return {"recovery_type": "unknown-owner"}
                existing = self._store.read_recovery_events(**identity)
                if existing:
                    return {"recovery_type": existing[-1]["event_type"], "recovered_from": existing[-1]["recovered_from"]}
                if receipt is not None:
                    state = "receipt_without_terminal"
                elif commit is not None:
                    state = "commit_without_receipt"
                else:
                    events = self._store.read_events(**identity)
                    state = "finalizing" if any(event["event_type"].startswith("finalization_") for event in events) else "unfinished"
                # A write may have reached the browser before its local finalization event.
                kind = "unresolved" if state != "unfinished" or start["risk_level"] == "r2-ui-write-test" else "interrupted"
                self._store.append_recovery_event_by_attempt_dir(
                    attempt_dir_name=derive_attempt_directory_name(**identity),
                    recovery_type=kind, recovered_from=state, code="E_PREVIOUS_ATTEMPT_" + kind.upper(),
                )
                return {"recovery_type": kind, "recovered_from": state}
        except FileLockBusy:
            return {"recovery_type": "active"}
        except (OSError, KeyError, ValueError, FinalizationStoreError):
            return {"recovery_type": "unknown-owner"}
