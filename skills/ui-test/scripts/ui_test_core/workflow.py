"""Advance an explicitly approved UI workflow using the selected suite's stage owners."""
import hashlib
from importlib import import_module
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from .artifact_layout import ProjectLayout, batch_stage_id, dispatch_task_ref
from .codex_dispatch_state import publish
from .routing import select_packet


def digest(content):
    return hashlib.sha256(content).hexdigest()


def path_in(project, relative):
    path = (project / relative).resolve()
    path.relative_to(project)
    if Path(relative).is_absolute() or path == project:
        raise ValueError("E_WORKFLOW_PROJECT_PATH")
    return path


def verify_files(project, bindings, required):
    if not isinstance(bindings, dict) or not set(required) <= bindings.keys():
        raise ValueError("E_WORKFLOW_FILE_BINDINGS: " + ", ".join(required))
    for name, expected in bindings.items():
        if digest(path_in(project, name).read_bytes()) != expected:
            raise ValueError("E_WORKFLOW_FILE_CHANGED: " + name)


def owned(suite, skill, module):
    return import_module(suite.load_package(skill).__name__ + "." + module)


def take_claim(path, identity):
    try:
        with path.open("x", encoding="utf8") as stream:
            json.dump(identity, stream)
        return True
    except FileExistsError:
        if json.loads(path.read_bytes()) != identity:
            raise ValueError("E_WORKFLOW_PREVIOUS_ATTEMPT: " + path.name)
        return False


def invoke(argv, project, env):
    # Native logs stay with the stage owner; the workflow returns its registered deliverables.
    return subprocess.run(argv, cwd=project, env=env, stdout=sys.stderr, check=False).returncode


def load_exploration(layout, run_id):
    folder = layout.run_dir("midscene", run_id)
    files = {key: folder / name for key, name in [
        ("observations", "observations.json"), ("evidence", "step-evidence.json"),
        ("stage", "stage.json"), ("report", "report.html")]}
    for path in files.values():
        if not path.is_file():
            raise ValueError("E_WORKFLOW_EXPLORATION_INCOMPLETE: " + str(path))
    record = json.loads(files["stage"].read_bytes())
    raw = files["observations"].read_bytes()
    obs = json.loads(raw)
    if (record["stage_type"], record["stage_id"], obs["stage"], obs["run_id"]) != (
            "midscene", run_id, "midscene", run_id):
        raise ValueError("E_WORKFLOW_EXPLORATION_IDENTITY")
    delivery = {key: str(path) for key, path in files.items()}
    return dict(delivery, observations_sha256=digest(raw), status=record["status"]), obs


def verify_checks(suite, observations, checks):
    review = owned(suite, "verify", "review_action").review_recorded_step
    return [review(observations, check) for check in checks]


def build_script(suite, build, project, env, observations, delivery):
    if not build.get("approval_ref") or build.get("observations_sha256") != delivery["observations_sha256"]:
        raise ValueError("E_WORKFLOW_BUILD_AUTHORIZATION_OR_OBSERVATIONS")
    keys = ["source", "test_data", "dependencies", "module_registry"]
    if build.get("runtime_material"):
        keys.append("runtime_material")
    verify_files(project, build["files"], [build[key] for key in keys] + ["ui-test.project.yaml"])
    checks = build["checks"]
    source = json.loads(path_in(project, build["source"]).read_bytes())
    if not checks or any((row["case_id"], row["branch_id"]) != (source["case_id"], source["branch_id"])
                         for row in checks):
        raise ValueError("E_WORKFLOW_BUILD_CASE_IDENTITY")
    reviews = verify_checks(suite, observations, checks)
    if any(review["status"] != "passed" for review in reviews):
        raise ValueError("E_WORKFLOW_BUILD_VERIFICATION_FAILED")
    argv = [sys.executable, str(suite.skill_path("script-build") / "scripts/compile_project_case.py"),
            "--project", str(project), "--display-name", build["display_name"]]
    for key in keys:
        argv += ["--" + key.replace("_", "-"), str(path_in(project, build[key]))]
    child = subprocess.run(argv, cwd=project, env=env, capture_output=True)
    if child.returncode:
        codes = re.findall(rb"\bE_[A-Z][A-Z0-9_]+", child.stderr)
        cause = codes[-1].decode("ascii") if codes else f"exit={child.returncode}"
        raise ValueError("E_WORKFLOW_BUILD_FAILED: " + cause)
    output = json.loads(child.stdout)
    release = Path(output["release_path"]).resolve()
    script = release / "playwright-test.py"
    return dict(release=str(release), script=str(script), sha256=digest(script.read_bytes()), checks=reviews)


def finish_formal(suite, project, layout, trace, env, formal, obs, delivery, fingerprint, result):
    nodes = formal["nodes"]
    selected = [row["node"] for row in nodes]
    if len(set(selected)) != len(selected) or any("::" not in node for node in selected):
        raise ValueError("E_WORKFLOW_FORMAL_NODE_IDENTITY")
    verify_files(project, formal["files"], [node.split("::")[0] for node in selected] + [
        name for name in ("conftest.py", "ui-test.project.yaml") if (project/name).exists()])
    checks = formal["checks"]
    if {(r["case_id"], r["branch_id"]) for r in nodes} != {(r["case_id"], r["branch_id"]) for r in checks}:
        raise ValueError("E_WORKFLOW_FORMAL_CASE_COVERAGE")
    reviews = verify_checks(suite, obs, checks)
    result["deliveries"]["verify"] = reviews
    if any(row["status"] != "passed" for row in reviews):
        raise ValueError("E_WORKFLOW_VERIFICATION_FAILED")
    batch = formal["batch"]
    task = trace / "formal-task.json"
    argv = [sys.executable, str(suite.skill_path("playwright-run")/"scripts/run.py"),
            "--task-ref", str(task), "--batch-ref", batch]
    for node in selected:
        argv += ["--node", node]
    if formal.get("parallel_intent"):
        intent = formal["parallel_intent"]
        verify_files(project, formal["files"], [intent])
        argv += ["--parallel-intent", str(path_in(project, intent))]
    if formal.get("r2_approved") is True:
        if not formal.get("write_budget_ref") or formal["write_budget_ref"] not in formal["files"]:
            raise ValueError("E_WORKFLOW_FORMAL_WRITE_BUDGET")
        argv += ["--", "--ui-r2-approved"]
    fresh = take_claim(trace / "formal-claim.json", dict(request_sha256=fingerprint, observed=delivery["observations_sha256"]))
    if fresh:
        code = invoke(argv, project, env)
        publish(trace / "formal-exit.json", {"exit": code})
    formal_stage = batch_stage_id(dispatch_task_ref(task), batch)
    folder = layout.run_dir("playwright", formal_stage)
    report = folder / "report.html"
    result["deliveries"]["playwright-run"] = dict(stage_id=formal_stage, task=str(task), nodes=selected,
                                                  report=str(report) if report.is_file() else None)
    if not (trace / "formal-exit.json").is_file():
        raise ValueError("E_WORKFLOW_FORMAL_EXIT_UNCONFIRMED: inspect current task before continuing")
    code = json.loads((trace / "formal-exit.json").read_bytes())["exit"]
    if code or not report.is_file():
        raise ValueError(f"E_WORKFLOW_FORMAL_INCOMPLETE: exit={code}")
    summary_path = folder / "execution-summary.json"
    summary = json.loads(summary_path.read_bytes())
    identities = {(row["node_id"], row["case_id"], row["branch_id"]) for row in summary["cases"]}
    wanted = {(row["node"], row["case_id"], row["branch_id"]) for row in nodes}
    if (summary["run_id"] != formal_stage or summary["stage"] != "playwright" or identities != wanted
            or len(summary["cases"]) != len(nodes) or not all(
                row["status"] == "passed" and row.get("run_result_hash") for row in summary["cases"])):
        raise ValueError("E_WORKFLOW_FORMAL_V5_IDENTITY")
    result["deliveries"]["playwright-run"]["summary"] = str(summary_path)


def workflow(suite, request_path, approved_sha256):
    raw = request_path.read_bytes()
    fingerprint = digest(raw)
    result = {"status": "stopped", "request_sha256": fingerprint, "deliveries": {}}
    if approved_sha256 != fingerprint:
        return dict(result, reason="E_WORKFLOW_APPROVAL_REQUIRED")
    request = json.loads(raw)
    try:
        project = Path(request["project"]).resolve(strict=True)
        if not Path(request["project"]).is_absolute() or Path(request["suite"]).resolve() != suite.root:
            raise ValueError("E_WORKFLOW_SELECTED_INSTALLATION")
        if not isinstance(request["scope"], dict) or not request["scope"].get("approval_ref"):
            raise ValueError("E_WORKFLOW_AUTHORIZATION_SCOPE")
        exp = request["explore"]
        run_id = exp["run_id"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id):
            raise ValueError("E_WORKFLOW_RUN_ID")
        layout = ProjectLayout(project)
        plan = request["plan"]
        verify_files(project, exp["files"], [plan["file"], exp["runner"]])
        source = json.loads(path_in(project, plan["file"]).read_bytes())
        if plan["kind"] == "source":
            packet, missing = owned(suite, "plan", "build_plan").build(source)
            if missing:
                return dict(result, reason="E_WORKFLOW_PLAN_MISSING", missing=missing)
        elif plan["kind"] == "packet":
            packet = source
        else:
            raise ValueError("E_WORKFLOW_PLAN_KIND")
        choice = select_packet(packet)
        if not choice["ok"] or choice["route"] != "explore" or packet["state"] in {"blocked", "done"}:
            raise ValueError("E_WORKFLOW_PACKET_NOT_READY_FOR_EXPLORATION")
        if packet["run"]["run_id"] != run_id:
            raise ValueError("E_WORKFLOW_PACKET_IDENTITY")
        trace = project / "临时" / "workflow" / run_id
        path_in(project, str(trace.relative_to(project)))
        trace.mkdir(parents=True, exist_ok=True)
        identity = dict(plan=plan, explore=exp, suite=str(suite.root), scope=request["scope"])
        binding = digest(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf8"))
        new = take_claim(trace / "explore-claim.json", {"binding_sha256": binding})
        result["deliveries"]["plan"] = str(trace / "packet.json")
        env = dict(os.environ, UI_TEST_SUITE=str(suite.root), UI_TEST_PROJECT=str(project),
                   UI_TEST_EXPLORATION_RUN_ID=run_id, UI_TEST_PYTHON=sys.executable,
                   UI_TEST_EXPLORE_ENTRY=str(suite.skill_path("explore") / "scripts/exploration_stage.cjs"),
                   PYTHONPATH=os.pathsep.join([str(suite.root), str(suite.root/"scripts"), os.environ.get("PYTHONPATH", "")]))
        if new:
            publish(trace / "explore-authorization.json", {"request_sha256": fingerprint, "binding_sha256": binding})
            publish(trace / "packet.json", packet)
            code = invoke([shutil.which("node") or "node", str(path_in(project, exp["runner"]))], project, env)
            publish(trace / "explore-exit.json", {"exit": code})
        if not new and not (trace / "explore-exit.json").is_file():
            raise ValueError("E_WORKFLOW_EXPLORATION_EXIT_UNCONFIRMED: inspect current attempt before continuing")
        delivery, obs = load_exploration(layout, run_id)
        result["deliveries"]["explore"] = delivery
        if json.loads((trace / "explore-exit.json").read_bytes())["exit"]:
            raise ValueError("E_WORKFLOW_EXPLORATION_REVIEW")
        if any(step.get("write_state") in {"unknown", "write_unconfirmed", "write_unknown", "write_outcome_unknown"}
               or step.get("status") == "unknown" for case in obs["cases"] for step in case["steps"]):
            raise ValueError("E_WORKFLOW_WRITE_OR_RESULT_UNKNOWN")
        if delivery["status"] != "observed":
            blocked = [{key: case.get(key) for key in ("case_id", "branch_id", "attempt_ref", "reason")}
                       for case in obs["cases"] if case["status"] == "blocked"]
            formal_review = (request.get("formal") or {}).get("reviewed_blockers")
            result["exploration_blockers"] = blocked
            if not blocked or formal_review != blocked or request.get("build"):
                raise ValueError("E_WORKFLOW_EXPLORATION_REVIEW")
        if request.get("build"):
            result["deliveries"]["script-build"] = build_script(suite, request["build"], project, env, obs, delivery)
        if not request.get("formal"):
            return dict(result, reason="E_WORKFLOW_FORMAL_MISSING", missing=["formal authorization, checks and selected nodes"])
        formal = request["formal"]
        if not formal.get("approval_ref") or not formal.get("checks") or not formal.get("nodes"):
            raise ValueError("E_WORKFLOW_FORMAL_PREREQUISITES: approval_ref, checks, nodes")
        if formal.get("observations_sha256") and formal["observations_sha256"] != delivery["observations_sha256"]:
            raise ValueError("E_WORKFLOW_FORMAL_OBSERVATIONS_CHANGED")
        finish_formal(suite, project, layout, trace, env, formal, obs, delivery, fingerprint, result)
        result["status"] = "completed"
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result["reason"] = str(exc)
    return result
