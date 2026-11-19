"""Persist reviewed UI strategies from a committed source-case execution."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .case_contracts import canonical_hash
from .reusable_assets import inside, SELECTION_SCOPE
from .run_evidence_linker import verify_run_result_v5_links


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _publish(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temp.write(json.dumps(document, ensure_ascii=False, indent=2).encode())
    staged = Path(temp.name)
    try:
        try:
            if os.name == "nt":
                staged.rename(path)  # Windows rename refuses to overwrite an existing decision.
            else:
                os.link(staged, path)  # Publish complete bytes with no overwrite on POSIX.
        except FileExistsError:
            if _read(path) != document:
                raise ValueError("experience identity conflict")
    finally:
        staged.unlink(missing_ok=True)


def applicable_experiences(project, scope, asset, build, *, trial=False):
    folder = Path(project) / "reuse-experiences"
    matches = []
    for path in sorted(folder.glob("candidates/*.json")):
        candidate = _read(path)
        if (candidate["scope"], candidate["asset"], candidate["build"]) != (scope, asset, build):
            continue
        identity = path.stem
        if canonical_hash(candidate).split(":")[-1] != identity:
            raise ValueError("experience identity mismatch")
        decisions = sorted((folder / "enabled" / identity).glob("*.json"))
        if decisions or trial:
            decision = _read(decisions[0]) if decisions else None
            if decision:
                validation = decision["validation"]
                expected_name = validation["result_hash"].split(":")[-1][:24]
                reused = any(validation[k] == candidate["source"][k] for k in ("run_id", "session_id", "attempt_ref"))
                if (decision["candidate_id"] != identity or decision["scope"] != scope or reused
                        or expected_name != decisions[0].stem or not decision["reason"]):
                    raise ValueError("experience decision mismatch")
            matches.append(dict(experience_id=identity, mode="enabled" if decision else "trial",
                                strategy=candidate["strategy"], pattern=candidate["pattern"],
                                decision_ref=decisions[0].relative_to(project).as_posix() if decisions else None))
    return matches


def choose_strategy(strategies, matches):
    """Select an implemented strategy and explain the scoped experience that affected it."""
    excluded = {m["strategy"] for m in matches if m["pattern"] == "failure"}
    permitted = [s for s in strategies if s not in excluded]
    preferred = {m["strategy"] for m in matches if m["pattern"] == "success"}
    selected = next((s for s in permitted if s in preferred), next(iter(permitted), None))
    feedback = []
    for match in matches:
        if match["pattern"] == "failure" and match["strategy"] in strategies:
            feedback.append(dict(match, disposition="exclude"))
        elif match["pattern"] == "success" and match["strategy"] == selected:
            feedback.append(dict(match, disposition="adopt"))
    return selected, feedback


def learn(project, run_root, step_id, *, candidate_id=None):
    """Learn a candidate or qualify one in exactly its original scope using a new execution."""
    run = Path(run_root).resolve()
    final = run / "finalization"
    commit = _read(final / "finalization-commit.json")
    result = _read(inside(final, commit["run_result_ref"]))
    if (result["run_result_hash"] != commit["run_result_hash"] or commit["run_id"] != run.name
            or verify_run_result_v5_links(result, run_root=run, expected_run_id=run.name)):
        raise ValueError("invalid committed run")
    step = next((s for s in result["step_results"] if s["step_id"] == step_id), {})
    ref = step.get("strategy_use_ref")
    if not ref or ref not in step["evidence_refs"]:
        raise ValueError("missing original strategy evidence")
    use = _read(inside(run, ref))
    snapshot = _read(inside(run, result["resolved_test_data_ref"]))
    if (canonical_hash(use) != step.get("strategy_use_hash")
            or any(use[k] != result[k] for k in ("case_id", "attempt_ref", "run_id"))
            or use["scope"]["step_id"] != step_id or use["scope"]["case_id"] != result["case_id"]
            or set(SELECTION_SCOPE) - use["scope"].keys() or not use["entered"]
            or snapshot["build_fingerprint"] != use["build"]):
        raise ValueError("unverified strategy evidence")
    passed = (result["overall_status"] == step["status"] == use["assertion_result"] == "passed"
              and use["action_result"] == "passed")
    if not passed and not (step["status"] == "failed" and use["assertion_result"] == "failed"):
        raise ValueError("strategy outcome unknown")
    source = dict(run_id=run.name, session_id=result["session_id"], attempt_ref=result["attempt_ref"],
                  step_id=step_id, evidence_refs=step["evidence_refs"], result_hash=result["run_result_hash"])
    folder = Path(project) / "reuse-experiences"
    scope, asset, build = use["scope"], use["asset"], use["build"]
    if candidate_id is None:
        candidate = dict(scope=scope, asset=asset, build=build, source=source,
                         pattern="success" if passed else "failure",
                         **{k: use[k] for k in ("condition", "strategy", "action", "expected", "actual")})
        identity = canonical_hash(candidate).split(":")[-1]
        _publish(folder / "candidates" / (identity + ".json"), candidate)
        return identity
    matches = applicable_experiences(project, scope, asset, build, trial=True)
    match = next((m for m in matches if m["experience_id"] == candidate_id), None)
    if not match or not passed:
        raise ValueError("missing successful scoped rerun")
    candidate = _read(folder / "candidates" / (candidate_id + ".json"))
    disposition = "adopt" if candidate["pattern"] == "success" else "exclude"
    if (any(candidate["source"][k] == source[k] for k in ("run_id", "session_id", "attempt_ref"))
            or not any(item["experience_id"] == candidate_id and item["strategy"] == candidate["strategy"]
                       and item["disposition"] == disposition and item["mode"] == "trial"
                       for item in use["experiences"])):
        raise ValueError("independent trial of this experience required")
    decision = dict(candidate_id=candidate_id, scope=scope, validation=source,
                    reason="Independent scope-matched trial passed the original case assertions.")
    _publish(folder / "enabled" / candidate_id / (result["run_result_hash"].split(":")[-1][:24] + ".json"), decision)
    return candidate_id


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("run_root", type=Path)
    parser.add_argument("step")
    parser.add_argument("--qualify", metavar="CANDIDATE_ID")
    args = parser.parse_args()
    print(learn(args.project, args.run_root, args.step, candidate_id=args.qualify))
