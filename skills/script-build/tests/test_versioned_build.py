"""Verify the public build/import contract on a synthetic source case."""
import importlib
from pathlib import Path
import sys

import pytest

MAIN = Path(__file__).resolve().parents[2] / "ui-test"
sys.path.insert(0, str(MAIN))
from scripts.ui_test_core.case_sync import apply_sync_plan, save_project_plan
from scripts.ui_test_core.compiler_v2 import compile_case_v2
from scripts.ui_test_core.suite import selected_suite
from tests.fixtures_v2 import compiled_v2, page_module_registry, source_case_v2, write_test_data


def test_compilation_stages_release_without_creating_a_formal_attempt(tmp_path):
    package = selected_suite().load_package("script-build")
    assert importlib.import_module(package.__name__ + ".compiler_v2").compile_case_v2 is compile_case_v2
    compiled, _ = compiled_v2(tmp_path / "test-data.json")
    plan = save_project_plan(tmp_path, compiled, "Sample")
    result = apply_sync_plan(plan, lambda: compiled, plan["target"])
    release = Path(result["release_path"])
    assert (release / "playwright-test.py").is_file()
    assert result["active_build"] == compiled["outputs"]["compile-receipt.json"]["build_fingerprint"]
    assert compiled["identity"]["dependency_digest"]
    assert not list(tmp_path.rglob("run-result*.json"))
    assert not (tmp_path / "运行").exists()


def test_missing_dependency_gives_source_id(tmp_path):
    source = source_case_v2()
    with pytest.raises(ValueError, match="E_DEPENDENCY_MISSING:flow.open-create"):
        compile_case_v2(source_case=source, test_data=write_test_data(tmp_path / "data.json"),
                        dependency_assets={}, page_module_registry=page_module_registry(),
                        config_fingerprint="sha256:" + "0" * 64,
                        runtime_values={"SERVICE_HOST": {"value": "example.test", "classification": "ordinary",
                                                         "sensitive": False}},
                        credential_keys={"shared-login"}, sequence_keys={"popup-version"})
