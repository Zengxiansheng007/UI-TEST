import hashlib
import json
from pathlib import Path
import subprocess
import sys


def test_redeliver_after_only_observations_were_saved(tmp_path):
    archive = tmp_path / "recovery"
    archive.mkdir()
    source = archive / "observations.json"
    case = dict(run_id="recovery", case_id="item", node_id="item", branch_id="main", attempt_ref="1",
                status="observed", steps=[dict(step_id="read", action="Inspect item")])
    original = json.dumps(dict(stage="midscene", run_id="recovery", cases=[case])).encode()
    source.write_bytes(original)
    publisher = Path(__file__).resolve().parents[1] / "scripts/publish_observations.py"
    command = [sys.executable, str(publisher), "--archive", str(source)]
    recovered = json.loads(subprocess.check_output(command))
    index = Path(recovered["step_evidence"])
    proof = json.loads(index.read_bytes())
    assert proof["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert [step["pointer"] for step in proof["steps"]] == ["/cases/0/steps/0"]
    modification_time = index.stat().st_mtime_ns
    assert json.loads(subprocess.check_output(command))["step_evidence"] == str(index)
    assert index.stat().st_mtime_ns == modification_time
    assert source.read_bytes() == original
