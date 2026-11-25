"""Compile and publish one case revision under the configured project."""
import argparse
import json
from pathlib import Path

from ui_test_core.case_sync import apply_sync_plan, save_project_plan
from ui_test_core.compiler_v2 import compile_case_v2
from ui_test_core.project_config import load_project_config
from ui_test_core.strict_json import load_strict_json
from ui_test_core.test_data_contracts import load_test_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--test-data", required=True, type=Path)
    parser.add_argument("--dependencies", required=True, type=Path)
    parser.add_argument("--module-registry", required=True, type=Path)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--runtime-material", type=Path, help="Local compiler material with runtime_values, credential_keys and sequence_keys")
    args = parser.parse_args()

    def load():
        config = load_project_config(args.project / "ui-test.project.yaml")
        execution_root = Path(config["asset_governance"]["execution_asset_root"]).resolve(strict=True)
        relative = args.project.resolve(strict=True).relative_to(execution_root)
        if not relative.parts or relative.parts[0].startswith("_"):
            raise ValueError("E_ARTIFACT_PROJECT_ROOT")
        source = load_strict_json(args.source)
        data = load_test_data(args.test_data, case_id=source["case_id"], branch_id=source["branch_id"])
        material = load_strict_json(args.runtime_material) if args.runtime_material else {}
        return compile_case_v2(source_case=source, test_data=data, dependency_assets=load_strict_json(args.dependencies),
                               page_module_registry=load_strict_json(args.module_registry),
                               config_fingerprint=config["config_fingerprint"], runtime_values=material.get("runtime_values"),
                               credential_keys=set(material.get("credential_keys", [])),
                               sequence_keys=set(material.get("sequence_keys", [])))

    plan = save_project_plan(args.project, load(), args.display_name)
    result = apply_sync_plan(plan, load, plan["target"])
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["status"] in {"in_sync", "applied"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
