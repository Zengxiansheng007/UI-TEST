import json
from pathlib import Path
import subprocess
import sys
import os

SKILLS = Path(__file__).resolve().parents[2]


def test_action_review_fallback_keeps_original(tmp_path):
    source = tmp_path / "action.json"
    source.write_text(json.dumps({"action": "submit", "expected": {"title": "Receipt"},
        "observed": {"title": "Pending"}, "evidence_ref": "before.png",
        "fallback": {"reason": "updated snapshot", "evidence_ref": "after.png",
                     "observed": {"title": "Receipt"}}}))
    proc = subprocess.run([sys.executable, str(SKILLS / "verify/scripts/review_action.py"),
                           "--input", str(source)], cwd=tmp_path, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(SKILLS / "ui-test/scripts")})
    assert proc.returncode == 0, proc.stderr
    record = json.loads(proc.stdout)
    assert record["status"] == "degraded"
    assert not record["primary"]["passed"] and record["fallback"]["passed"]
    assert record["repeat_action"] is False


def test_unknown_submit_stops_and_missing_assertion_explained(tmp_path):
    source = tmp_path / "action.json"
    for expected, reason in [({}, "E_STEP_POSTCONDITION_MISSING"),
                              ({"title": "Receipt"}, "E_POSTCONDITION_MISMATCH")]:
        source.write_text(json.dumps({"action": "submit", "expected": expected, "observed": {},
                                     "evidence_ref": "after.png"}))
        proc = subprocess.run([sys.executable, str(SKILLS / "verify/scripts/review_action.py"),
                               "--input", str(source)], cwd=tmp_path, capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": str(SKILLS / "ui-test/scripts")})
        assert proc.returncode != 0
        assert reason in proc.stderr + proc.stdout
