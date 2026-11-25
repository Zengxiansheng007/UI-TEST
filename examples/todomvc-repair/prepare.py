"""Prepare an independent project, qualify the candidate, and promote it using saved proof."""
import argparse
import json
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent
sys.path.insert(0, str(TEMPLATE.parents[1] / "skills/ui-test/scripts"))
from source_case import BINDINGS, CASE, SCOPE
from ui_test_core.asset_repair import committed_use, impact_plan, repair_destination, require_verified
from ui_test_core.asset_revision import AssetCatalog, digest, encoded, replace
from ui_test_core.artifact_layout import ProjectLayout

KEY = "locator.target"


def initialize(project, ownership="project"):
    project.mkdir(parents=True, exist_ok=False)
    for name in ("conftest.py", "source_case.py", "test_complete.py", "formal_result.py"):
        shutil.copy2(TEMPLATE/name, project/name)
    shutil.copy2(TEMPLATE.parent/"todomvc/todomvc_page.py", project/"todomvc_page.py")
    import yaml
    config = yaml.safe_load((TEMPLATE.parent/"todomvc/ui-test.project.yaml").read_text(encoding="utf-8"))
    config["stage_write_policies"] = [dict(case_id=CASE,branch_id="primary",phase_ids=["add-other","add-target","check-target"])]
    config["scope"]["project_group"] = SCOPE["project_group"]
    (project/"ui-test.project.yaml").write_text(yaml.safe_dump(config,allow_unicode=True),encoding="utf-8")
    shutil.copytree(TEMPLATE/"assets", project/"assets")
    assets = {}
    for key, filename, kind, symbol, dependencies in (
        (KEY, "target.py", "locator", "Target.__init__.row", []),
        ("component.ready", "actions.py", "component", "unique_row", [KEY]),
        ("script.complete", "actions.py", "script", "check_target", ["component.ready"]),
    ):
        source = project/"assets"/filename
        recovery = Path("versions")/"1"/filename
        replace(project/recovery, source.read_bytes())
        assets[key] = dict(symbol=symbol, kind=kind, source=filename, recovery_source=recovery.as_posix(),
                           sha256=digest(source.read_bytes()), version=1, enabled=True, conditions={"environment":"test"},
                           owner={k:SCOPE[k] for k in ("project_group","product")}, prerequisites=[], inputs=["page"],
                           side_effects="UI write" if kind == "script" else "read", steps=["COMPLETE"],
                           paused_scopes=[], dependencies=dependencies)
    assets[KEY]["source_ownership"] = ownership
    assets[KEY]["conditions"] = dict(SCOPE)  # This copy has one source case and one enabled scope.
    replace(project/"reuse-project.json", encoded(dict(directory="assets", assets=assets)))


def stage(project, trial, failure_run):
    catalog = AssetCatalog(project)
    revision, rows = catalog.pin()
    if not catalog.paused(KEY, 1, SCOPE) or rows[KEY]["version"] != 1 or rows[KEY]["conditions"] != SCOPE:
        raise ValueError("stage requires a confirmed failure of the original scoped version")
    if not failure_run or not failure_run.isalnum():
        raise ValueError("expected original failure run")
    failure, failure_result = committed_use(project,failure_run,"failed")
    if (failure.get("failure", {}).get("cause") != "asset" or failure.get("matches") != 2
            or failure.get("scope") != SCOPE or failure.get("version") != 1
            or failure.get("sha256") != rows[KEY]["sha256"] or failure.get("run_id") != failure_run
            or failure.get("writes") != ["add", "add"] or failure.get("action_result") != "not_attempted"
            or failure.get("source_hash") != digest((project/"source_case.py").read_bytes())):
        raise ValueError("failure evidence does not authorize this repair")
    plan = impact_plan(rows, KEY, BINDINGS)
    if plan["unresolved"] or plan["cases"] != [CASE]:
        raise ValueError("affected cases not fully mapped")
    shutil.copytree(project, trial, ignore=shutil.ignore_patterns("运行", "临时", "runs", "execution-evidence", "__pycache__", ".pytest_cache"))
    destination = repair_destination(rows[KEY].get("source_ownership"))
    raw = (TEMPLATE/"repairs"/destination/"target.py").read_bytes()
    source = Path(destination)/"2"/"target.py"
    replace(trial/"assets"/source, raw)
    desc = dict(rows[KEY], version=2, sha256=digest(raw), conditions=SCOPE, source=source.as_posix(),
                adapted_from=dict(asset_id=KEY, version=1, sha256=rows[KEY]["sha256"]),
                failure_ref=(ProjectLayout(project).find_attempt(failure_run)/"use.json").relative_to(project.resolve()).as_posix(), failure_sha256=digest(encoded(failure)),
                failure_result_hash=failure_result)
    AssetCatalog(trial).publish(KEY, desc, raw, expected_revision=revision)
    replace(trial/"qualification.json", encoded(dict(plan=plan, expected_revision=revision,
            source_hash=digest((project/"source_case.py").read_bytes()), destination=destination)))


def promote(project, trial, proof_run):
    catalog, trial_catalog = AssetCatalog(project), AssetCatalog(trial)
    revision, rows = catalog.pin()
    _, tested = trial_catalog.pin()
    gate = json.loads((trial/"qualification.json").read_bytes())
    if not proof_run or not proof_run.isalnum():
        raise ValueError("expected an alphanumeric qualification run")
    proof, trial_result = committed_use(trial,proof_run,"passed")
    plan = impact_plan(rows, KEY, BINDINGS)
    if (revision != gate["expected_revision"] or gate["plan"] != plan or plan["unresolved"]
            or plan["cases"] != [CASE] or proof["run_id"] != proof_run
            or proof["entries"] != [KEY, "script.complete", "component.ready"]
            or proof["before"] != [False,False,"2 items left"] or proof["after"] != [True,False,"1 item left"]):
        raise ValueError("regression proof or revision is incomplete")
    for name in ("source_case.py", "test_complete.py", "todomvc_page.py","conftest.py","formal_result.py","ui-test.project.yaml"):
        if (project/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError("project case or runtime differs from tested source")
    row = tested[KEY]
    require_verified(KEY, row, SCOPE, proof, source_hash=digest((project/"source_case.py").read_bytes()),
                     paused=catalog.paused(KEY,row["version"],SCOPE) or trial_catalog.paused(KEY,row["version"],SCOPE))
    raw = (trial/row["recovery_source"]).read_bytes()
    from ui_test_core.reusable_assets import inside
    target = inside((project/"assets").resolve(), row["source"])
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("candidate source path already contains a different version")
    replace(target, raw)
    row = dict(row, regression_proof={"run_id": proof_run, "sha256": digest(encoded(proof)),
                                     "source_hash": proof["source_hash"], "cases": plan["cases"],"result_hash":trial_result})
    catalog.publish(KEY, row, raw, expected_revision=revision)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["initialize","stage","promote"])
    parser.add_argument("project", type=Path)
    parser.add_argument("--trial", type=Path)
    parser.add_argument("--proof-run")
    parser.add_argument("--failure-run")
    parser.add_argument("--ownership", choices=["project", "external", "unknown"], default="project")
    args = parser.parse_args()
    if args.action == "initialize":
        initialize(args.project, args.ownership)
    elif args.action == "stage":
        stage(args.project, args.trial, args.failure_run)
    else:
        promote(args.project,args.trial,args.proof_run)
