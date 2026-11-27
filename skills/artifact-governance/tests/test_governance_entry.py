"""Exercise governance through its selected owner and the historical public CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys

SKILLS = Path(__file__).resolve().parents[2]
MAIN = SKILLS / "ui-test"


def test_selected_governance_and_legacy_inventory(tmp_path):
    env = dict(os.environ, UI_TEST_SUITE=str(MAIN), PYTHONIOENCODING="utf8")
    suite = MAIN / "scripts/ui_test_suite.py"
    result = subprocess.run([sys.executable, str(suite), "resolve", "artifact-governance"],
                            env=env, capture_output=True, encoding="utf8")
    assert result.returncode == 0, result.stderr
    owner = Path(json.loads(result.stdout)["skill"])
    assert owner == SKILLS / "artifact-governance"
    for entry in (owner, MAIN):
        run = subprocess.run([sys.executable, str(entry / "scripts/project_governance.py"), "inventory", str(tmp_path)],
                             env=env, capture_output=True, encoding="utf8")
        assert run.returncode == 0, run.stderr
        assert Path(run.stdout.strip()).is_file()


def test_release_without_approval_preserves_original(tmp_path):
    document = tmp_path / "historical.html"
    document.write_bytes(b"<html>original</html>")
    env = dict(os.environ, UI_TEST_SUITE=str(MAIN), PYTHONIOENCODING="utf8")
    entry = SKILLS / "artifact-governance/scripts/project_governance.py"
    result = subprocess.run([sys.executable, str(entry), "release", str(tmp_path), "a" * 20],
                            env=env, capture_output=True, encoding="utf8")
    assert result.returncode != 0 and "E_ARCHIVE_APPROVAL_MISSING" in result.stderr
    assert document.read_bytes() == b"<html>original</html>"
