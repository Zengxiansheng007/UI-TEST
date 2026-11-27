import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib
import importlib

import pytest

ROOT = Path(__file__).resolve().parents[3]


def invoke(skill, *args):
    env = dict(os.environ, UI_TEST_SUITE=str(ROOT / "skills/ui-test"),
               PYTHONPATH=str(ROOT / "skills/ui-test/scripts") + os.pathsep + os.environ.get("PYTHONPATH", ""))
    return subprocess.run([sys.executable, str(ROOT / "skills" / skill / "scripts" / "inspect_steps.py"),
                           *map(str, args)], capture_output=True, text=True, env=env)


def sample(path):
    step = {"step_id": "S1", "status": "failed", "reason": "locator_drift",
            "network_evidence": {"source": "page-response", "request_matched": True,
                                 "response_matched": True, "run_id": "R", "session_id": "SS",
                                 "status": 200, "evidence_ref": "response-abc", "headers": {"Cookie": "private-marker"}}}
    path.write_text(json.dumps({"stage": "midscene", "run_id": "R", "session_id": "SS",
                                "cases": [{"case_id": "C", "branch_id": "B", "attempt_ref": "A",
                                           "run_id": "R", "steps": [step]}]}), encoding="utf8")


def test_step_identity_and_safe_network_projection(tmp_path):
    source = tmp_path / "observations.json"
    sample(source)
    result = invoke("evidence", source)
    assert result.returncode == 0, result.stderr
    row, = json.loads(result.stdout)["steps"]
    assert [row[k] for k in ("run_id", "case_id", "branch_id", "attempt_ref", "step_id")] == list("RCBA") + ["S1"]
    assert row["network"]["status"] == 200 and row["screenshot_missing"] == "not-produced"
    assert "private-marker" not in result.stdout


def test_stale_response_and_foreign_image(tmp_path):
    source = tmp_path / "observations.json"
    sample(source)
    batch = json.loads(source.read_text("utf8"))
    step = batch["cases"][0]["steps"][0]
    step["network_evidence"]["run_id"] = "OTHER"
    source.write_text(json.dumps(batch), "utf8")
    current = invoke("evidence", source)
    row, = json.loads(current.stdout)["steps"]
    assert row["network"] is None and row["network_missing"] == "no-matched-page-response"
    step["images"] = [{"attempt_ref": "OTHER", "path": "a.png"}]
    source.write_text(json.dumps(batch), "utf8")
    conflict = invoke("evidence", source)
    assert conflict.returncode == 2 and conflict.stderr.strip() == "E_IMAGE_OWNER"


def test_formal_images_require_this_steps_binding(tmp_path, monkeypatch):
    scripts = ROOT / "skills/ui-test/scripts"
    monkeypatch.syspath_prepend(str(scripts))
    monkeypatch.setenv("UI_TEST_SUITE", str(scripts.parent))
    owner = importlib.import_module("ui_test_core.suite").selected_suite().load_package("evidence")
    picture = tmp_path / "other-step.png"
    picture.write_bytes(b"controlled bytes")
    digest = hashlib.sha256(picture.read_bytes()).hexdigest()
    step = {"images": [{"path": picture.name, "sha256": digest}], "evidence_refs": []}
    with pytest.raises(ValueError, match="E_STAGE_IMAGE_REF"):
        owner.pictures(step, {}, tmp_path, [picture.name])
    step["evidence_refs"] = [picture.name]
    assert owner.pictures(step, {}, tmp_path, [picture.name]) == [{"path": picture.name, "sha256": digest}]
    del step["images"]
    assert owner.pictures(step, {}, tmp_path, [picture.name]) == [{"missing_reason": "see-original"}]
