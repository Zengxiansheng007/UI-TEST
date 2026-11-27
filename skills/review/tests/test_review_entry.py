import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]


def run(name, *args):
    env = os.environ.copy()
    env["UI_TEST_SUITE"] = str(ROOT / "skills/ui-test")
    env["PYTHONPATH"] = str(ROOT / "skills/ui-test/scripts") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, str(ROOT / "skills" / name / "scripts/inspect_steps.py"), *map(str, args)],
                          capture_output=True, text=True, env=env)


def write_original(tmp, reasons):
    picture = tmp / "before.png"
    picture.write_bytes(b"controlled image attachment")
    steps = [{"step_id": f"S{i}", "status": "failed", "reason": reason,
              "images": [{"path": picture.name, "sha256": hashlib.sha256(picture.read_bytes()).hexdigest()}]}
             for i, reason in enumerate(reasons)]
    source = tmp / "observations.json"
    source.write_text(json.dumps(dict(stage="midscene", run_id="R", cases=[
        dict(run_id="R", case_id="C", attempt_ref="A", steps=steps)])), "utf8")
    return source


def test_review_direct_sealed_index_and_aliases(tmp_path):
    source = write_original(tmp_path, ["locator_drift", "environment_unavailable", "data_stale",
                                       "business_assertion_mismatch", "timeout"])
    before = source.read_bytes()
    index = run("evidence", source)
    assert index.returncode == 0, index.stderr
    assert json.loads(index.stdout)["steps"][0]["screenshots"][0]["path"] == "before.png"
    assert run("ui-test-evidence", source).stdout == index.stdout
    direct = run("review", source)
    assert direct.returncode == 0, direct.stderr
    findings = json.loads(direct.stdout)["findings"]
    assert [item["category"] for item in findings] == ["asset", "environment", "data", "business", "unknown"]
    assert findings[-1]["basis"]["source_pointer"] == "/cases/0/steps/4"
    indexed = tmp_path / "evidence.json"
    indexed.write_text(index.stdout, "utf8")
    assert run("ui-test-review", indexed).stdout == direct.stdout
    assert run("review", indexed).stdout == direct.stdout
    assert source.read_bytes() == before
    source.write_bytes(before.replace(b"locator_drift", b"data_stale"))
    stale = run("review", indexed)
    assert stale.returncode == 2 and "E_REVIEW_ORIGINAL_MISMATCH" in stale.stderr


@pytest.mark.parametrize("skill", ["evidence", "ui-test-evidence", "review", "ui-test-review"])
def test_missing_original(skill, tmp_path):
    result = run(skill, tmp_path / "absent.json")
    assert result.returncode == 2 and result.stderr.strip() == "E_STEP_FILE_MISSING"
