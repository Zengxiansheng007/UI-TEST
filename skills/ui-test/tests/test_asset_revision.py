import hashlib
import json
import subprocess
import sys

import pytest

from ui_test_core.asset_revision import AssetCatalog, RevisionConflict, deliver_event


def test_publish_pins_old_graph_and_rejects_stale_decision(tmp_path):
    source = b"def open_page(): pass\n"
    for name in ("entry.py", "recover.py"):
        (tmp_path / name).write_bytes(source)
    row = dict(symbol="open_page", sha256=hashlib.sha256(source).hexdigest(), kind="navigation",
               source="entry.py", recovery_source="recover.py", version=1, enabled=True,
               dependencies=[], steps=["OPEN"], conditions={}, paused_scopes=[])
    (tmp_path / "reuse-project.json").write_text(json.dumps(dict(directory=".", assets={"open": row})))
    store = AssetCatalog(tmp_path)
    rev, pinned = store.pin()
    new_source = source + b"# second version\n"
    next_row = dict(row, version=2, sha256=hashlib.sha256(new_source).hexdigest())
    assert store.publish("open", next_row, new_source, expected_revision=rev) == 1
    with pytest.raises(RevisionConflict):
        store.pause("open", 1, {"step_id": "OPEN"}, expected_revision=rev)
    assert pinned["open"]["version"] == 1
    assert store.pin()[1]["open"]["version"] == 2
    assert store.pause("open", 1, {"step_id": "OPEN"}, expected_revision=1) == 2
    assert store.paused("open", 1, {"step_id": "OPEN"})
    assert not store.paused("open", 2, {"step_id": "OPEN"})


def test_two_writer_processes_and_interrupted_manifest(tmp_path):
    (tmp_path / "reuse-project.json").write_text(json.dumps(dict(directory=".", assets={})))
    writer = """
import hashlib, os, sys
import ui_test_core.asset_revision as rev
project, mode = sys.argv[1:]
data = b'def run(): pass'
row = dict(symbol='run', sha256=hashlib.sha256(data).hexdigest(), kind='script',
           source='entry.py', version=1, enabled=True, dependencies=[], steps=['RUN'],
           conditions={}, paused_scopes=[])
original = rev.replace
def interrupt(path, content):
    if path.name == 'current.json' and mode == 'interrupt':
        os._exit(43)
    original(path, content)
rev.replace = interrupt
try:
    rev.AssetCatalog(project).publish('script', row, data, expected_revision=0)
except rev.RevisionConflict:
    sys.exit(42)
"""
    cmd = [sys.executable, "-B", "-c", writer, str(tmp_path)]
    assert subprocess.run(cmd + ["interrupt"], check=False).returncode == 43
    reader = [sys.executable, "-B", "-c",
              "from ui_test_core.asset_revision import AssetCatalog; import sys; "
              "rev, rows = AssetCatalog(sys.argv[1]).pin(); print(rev, sorted(rows))", str(tmp_path)]
    assert subprocess.check_output(reader, text=True).strip() == "0 []"
    writers = [subprocess.Popen(cmd + ["publish"]) for _ in range(2)]
    assert sorted(proc.wait(timeout=30) for proc in writers) == [0, 42]
    assert subprocess.check_output(reader, text=True).strip() == "1 ['script']"


def test_duplicate_delivery_retains_both_conflicting_payloads(tmp_path):
    event = dict(run_id="run", step_id="step", attempt_ref="attempt", sequence=0, status="started")
    assert deliver_event(tmp_path, event) == "recorded"
    assert deliver_event(tmp_path, event) == "duplicate"
    changed = dict(event, status="passed")
    assert deliver_event(tmp_path, changed) == "conflict"
    assert deliver_event(tmp_path, changed) == "conflict"
    assert [json.loads(p.read_bytes()) for p in (tmp_path / "conflicts").iterdir()] == [changed]
    assert deliver_event(tmp_path, event) == "duplicate"

