"""Exercise the public lookup and legacy rebuild against immutable project originals."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

SKILLS = Path(__file__).resolve().parents[2]
CMD = SKILLS / "run-catalog/scripts/project_catalog.py"
LEGACY = SKILLS / "ui-test/scripts/project_catalog.py"


def cli(project, *args, command=CMD):
    env = dict(os.environ, UI_TEST_SUITE=str(SKILLS / "ui-test"), PYTHONPATH=str(SKILLS / "ui-test/scripts"),
               PYTHONIOENCODING="utf8")
    return subprocess.check_output([sys.executable, command, project, *args], env=env, encoding="utf8").strip()


def seed(root, stage):
    sys.path.insert(0, str(SKILLS / "ui-test/scripts"))
    from ui_test_core.artifact_layout import ProjectLayout
    folder = ProjectLayout(root).reserve_run("playwright", stage)
    script = root / "versions/v1.py"
    script.parent.mkdir(exist_ok=True)
    script.write_bytes(b"print(1)")
    (root / "active.py").write_bytes(b"print(2)")
    (folder / "report.html").write_text("Stage report")
    binding = dict(entry="versions/v1.py", source="active.py", node_id="test_one",
                   sha256=hashlib.sha256(script.read_bytes()).hexdigest(), dependencies=[])
    attempt = dict(attempt_ref="try1", status="passed", version="V1", binding=binding)
    case = dict(case_id="C1", branch_id="main", status="passed", attempts=[attempt])
    record = dict(stage_id=stage, stage_type="playwright", status="passed", cases=[case],
                  report_ref=(folder / "report.html").relative_to(root).as_posix())
    file = folder / "stage.json"
    file.write_text(json.dumps(record), encoding="utf8")
    return file


def test_real_entries_and_historical_selection(tmp_path):
    first = seed(tmp_path, "one")
    cli(tmp_path, command=LEGACY)
    direct = json.loads(cli(tmp_path, "--original", str(first)))
    by_id = json.loads(cli(tmp_path, "--stage", "one"))
    assert direct == by_id
    row = by_id["matches"][0]["attempts"][0]
    assert (row["version"], row["entry"]) == ("V1", "versions/v1.py")
    assert (tmp_path / row["entry"]).read_bytes() == b"print(1)"
    seed(tmp_path, "two")
    ambiguous = json.loads(cli(tmp_path, "--case", "C1"))
    assert ambiguous["status"] == "ambiguous"
    assert [match["stage_id"] for match in ambiguous["matches"]] == ["one", "two"]
    (tmp_path / row["entry"]).unlink()
    missing = json.loads(cli(tmp_path, "--stage", "one"))
    assert "versions/v1.py" in missing["missing"]
    assert "active.py" not in missing["missing"]
    assert json.loads(cli(tmp_path, "--stage", "unknown"))["status"] == "not_found"
    with sqlite3.connect(tmp_path / "runs.sqlite3") as db:
        assert db.execute("SELECT stage_id, case_id, version FROM run_attempts ORDER BY stage_id").fetchall() == [
            ("one", "C1", "V1"), ("two", "C1", "V1")]
    assert "C1" in (tmp_path / "index.html").read_text(encoding="utf8")


def test_lookup_preserves_unexecuted_branch_without_counting_an_attempt(tmp_path):
    original = seed(tmp_path, "partial")
    doc = json.loads(original.read_bytes())
    doc["cases"].append(dict(case_id="C2", branch_id="reserved", status="not-executed", attempts=[]))
    original.write_text(json.dumps(doc), encoding="utf8")

    case = json.loads(cli(tmp_path, "--case", "C2"))["matches"][0]
    assert case["attempts"] == []
    expected = dict(case_id="C2", branch_id="reserved", case_status="not-executed")
    assert case["cases"] == [expected]
    stage = json.loads(cli(tmp_path, "--stage", "partial"))["matches"][0]
    assert stage["cases"] == [dict(case_id="C1", branch_id="main", case_status="passed"), expected]
    assert [attempt["attempt_ref"] for attempt in stage["attempts"]] == ["try1"]
