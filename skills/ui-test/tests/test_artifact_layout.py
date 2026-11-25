import json
import tempfile
import unittest
import pytest
from pathlib import Path

from scripts.ui_test_core.artifact_layout import ProjectLayout, checked_path

pytest_plugins = ["pytester"]


class ProjectLayoutTests(unittest.TestCase):
    def test_same_name_and_rename_preserve_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = ProjectLayout(directory)
            title = "相同的中文显示名😀" * 40
            first = layout.register_case("C1", "main", title)
            second = layout.register_case("C2", "main", title)
            self.assertNotEqual(first, second)
            self.assertEqual(first, layout.register_case("C1", "main", "新名称"))
            self.assertEqual(json.loads((first / "case.json").read_text("utf8"))["display_name"], "新名称")
            self.assertEqual(first.parent.name, "用例")
            self.assertEqual(layout.run_dir("midscene", "a" * 128).parent.name, "运行")
            self.assertEqual(layout.temp_dir("a" * 128).parent.name, "临时")
            for path in (first, second, layout.run_dir("midscene", "a" * 128)):
                self.assertLessEqual(len(str(path).encode("utf-16-le")) // 2, 220)

    def test_tool_suffix_budget_measures_utf16(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ("😀" * 92)
            with self.assertRaisesRegex(ValueError, "E_ARTIFACT_PATH_BUDGET"):
                checked_path(path, extra_units=40)


def test_formal_collection_loads_two_release_scripts_with_identical_filenames(pytester):
    pytester.makeconftest("pytest_plugins = ['ui_test_core.pytest_runtime_plugin']")
    nodes = []
    for name in ("alpha", "beta"):
        script = pytester.path / "releases" / name / "playwright-test.py"
        script.parent.mkdir(parents=True)
        script.write_text("def test_" + name + "(): pass", encoding="utf8")
        nodes.append(str(script))
    result = pytester.runpytest_subprocess("--collect-only", "-q", *nodes)
    assert result.ret == 0
    result.stdout.fnmatch_lines(["*::test_alpha", "*::test_beta"])
    assert not list((pytester.path / "releases").rglob("*.pyc"))


@pytest.mark.parametrize("marker", ["attempt", "runs/run41/use.json", "cases/a/runs/run41/pending.json",
                                    "cases/a/runs/run41/approval-record.json", "cases/a/runs/run41/execution-started"])
def test_historical_owner_rejects_before_new_attempt(tmp_path, marker):
    from scripts.ui_test_core.execution_attempt_store import ExecutionAttemptStore, ExecutionAttemptStoreError, derive_attempt_directory_name
    identity = dict(run_id="run41", node_id="test_example.py::test_a")
    if marker == "attempt":
        prior = tmp_path / "execution-evidence" / "attempts" / derive_attempt_directory_name(**identity) / "attempt-start.json"
    else:
        prior = tmp_path / marker
    prior.parent.mkdir(parents=True)
    prior.write_bytes(b"original")
    root = tmp_path / "运行" / "执行证据"
    store = ExecutionAttemptStore(evidence_root=root)
    with pytest.raises(ExecutionAttemptStoreError, match="E_ATTEMPT_START_ALREADY_EXISTS"):
        with store.attempt_ownership(**identity, case_id="a"):
            pytest.fail("historical run entered actions")
    assert not (root / "attempts").exists()
    assert prior.read_bytes() == b"original"
