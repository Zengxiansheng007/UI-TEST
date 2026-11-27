"""Static, project-local queries for reusable UI assets."""
import ast
import base64
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from ui_test_core.reuse_outcome import is_paused


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("asset path outside project")
    return path


def matches(path, row):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        return False
    try:
        nodes = ast.parse(raw).body
    except (SyntaxError, ValueError):
        return False
    parts = row["symbol"].split(".")
    for index, part in enumerate(parts):
        if index == len(parts) - 1 and row["kind"] == "locator":
            targets = [target for node in nodes if isinstance(node, ast.Assign) for target in node.targets]
            return sum(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                       and t.value.id == "self" and t.attr == part for t in targets) == 1
        found = [node for node in nodes if getattr(node, "name", None) == part]
        if len(found) != 1:
            return False
        nodes = getattr(found[0], "body", ())
    return True


def candidate_symbols(raw):
    try:
        body = ast.parse(raw).body
    except (ValueError, SyntaxError):
        return [], "unparseable_source"
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    symbols = []
    for node in body:
        if isinstance(node, functions):
            symbols.append(node.name)
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)
            symbols.extend(f"{node.name}.{child.name}" for child in node.body if isinstance(child, functions))
    return symbols, "undeclared_source" if symbols else "no_recognizable_symbol"


def register_candidates(root, directory, files, rows, *, persist=True):
    archive = inside(root, ".reuse-candidates")
    known = {inside(directory, row["source"]) for row in rows.values() if row["status"] == "available"}
    changed = {inside(directory, row["source"]) for row in rows.values() if row["status"] == "modified_candidate"}
    for file in files:
        if file in known:
            continue
        source = file.relative_to(root).as_posix()
        raw = file.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        identity = hashlib.sha256((source + "\0" + sha).encode()).hexdigest()
        path = inside(root, archive / (identity[:32] + ".json"))  # 兼容 Windows 长项目路径，记录内保留完整身份摘要。
        if path.is_file():
            if json.loads(path.read_text(encoding="utf-8"))["candidate"]["identity"] != identity:
                raise ValueError("candidate identity filename collision")
            continue
        symbols, reason = candidate_symbols(raw)
        candidate = dict(identity=identity, source=source, sha256=sha, symbols=symbols,
                         kind="unclassified", version=sha, dependencies=[], steps=[],
                         reason="externally_modified_source" if file in changed else reason,
                         recovery_source=path.relative_to(root).as_posix())
        if not persist:
            candidate["recovery_source"] = None
            rows["candidate:" + identity] = dict(candidate, status="candidate", enabled=False)
            continue
        archive.mkdir(exist_ok=True)
        with NamedTemporaryFile("w", dir=archive, encoding="utf-8", delete=False) as temp:
            json.dump({"candidate": candidate, "content_base64": base64.b64encode(raw).decode("ascii")}, temp)
        Path(temp.name).replace(path)  # 相同内容与来源对应同一份完整快照。
    for path in sorted(archive.glob("*.json")):
        saved = json.loads(inside(root, path).read_text(encoding="utf-8"))["candidate"]
        rows["candidate:" + saved["identity"]] = dict(saved, status="candidate", enabled=False)


def discover(project, *, state=None, persist_candidates=True):
    root = Path(project).resolve()
    from .asset_revision import AssetCatalog
    catalog = AssetCatalog(root)
    if state is None:
        state = catalog.state()
    config = json.loads((root / "reuse-project.json").read_text(encoding="utf-8-sig"))
    directory = inside(root, config["directory"])
    excludes = {inside(directory, path) for path in config.get("exclude_paths", [])}
    def included(path):
        resolved = path.resolve()
        return resolved.is_relative_to(directory) and not any(resolved.is_relative_to(p) for p in excludes)
    declarations = {key: [("reuse-project.json", row)] for key, row in config["assets"].items()}
    for sidecar in sorted(directory.rglob("*.asset.json")):
        if not included(sidecar):
            continue
        for key, row in json.loads(sidecar.read_text(encoding="utf-8-sig"))["assets"].items():
            declarations.setdefault(key, []).append((sidecar.relative_to(root).as_posix(), row))
    recoveries = {inside(root, row["recovery_source"]) for records in declarations.values()
                  for _, row in records}
    files = [p for p in directory.rglob("*.py")
             if included(p) and p.resolve() not in recoveries]
    rows = {}
    for key, records in declarations.items():
        declaration, declared = records[0]
        row = dict(declared)
        row["declarations"] = [name for name, _ in records]
        if len(records) > 1:
            rows[key] = dict(row, enabled=False, status="ambiguous")
            continue
        source = inside(directory, row["source"])
        frozen = inside(root, row["recovery_source"])
        if not frozen.is_file() or not matches(frozen, row):
            status = "missing_version"
        elif source in files:
            status = "available" if matches(source, row) else "modified_candidate"
        else:
            locations = [p for p in files if matches(p, row)]
            status = {0: "missing_source", 1: "available"}.get(len(locations), "ambiguous")
            if len(locations) == 1:
                row["source"] = locations[0].relative_to(directory).as_posix()
        if declaration != "reuse-project.json":
            row["enabled"] = False  # 新发现的独立声明须经项目核准后才能启用。
            if status == "available":
                status = "candidate"
        rows[key] = dict(row, status=status)
    register_candidates(root, directory, files, rows, persist=persist_candidates)
    for key, entry in state["assets"].items():
        source = inside(root, entry["recovery_source"])
        valid = source.is_file() and matches(source, entry)
        rows[key] = dict(entry, status="available" if valid else "missing_version")
    return rows


def dependents(rows, key):
    found = set()
    pending = [key]
    while pending:
        dependency = pending.pop()
        for name, row in rows.items():
            if dependency in row["dependencies"] and name not in found:
                found.add(name)
                pending.append(name)
    return sorted(found - {key})


def _available(project, rows, asset_id, scope):
    checked = set()
    pending = [asset_id]
    while pending:
        key = pending.pop()
        if key in checked:
            continue
        checked.add(key)
        if key not in rows:
            raise ValueError(f"{key}: missing declaration; affected steps {rows.get(asset_id, {}).get('steps', [])}")
        row = rows[key]
        if row["status"] != "available":
            raise ValueError(f"{key}: {row['status']} affected steps {row['steps']}")
        if not row["enabled"]:
            raise ValueError(f"{key}: disabled; affected steps {row['steps']}")
        if any(scope.get(k) != v for k, v in row["conditions"].items()):
            raise ValueError(f"{key}: conditions not met; affected steps {row['steps']}")
        if (any(all(scope.get(k) == v for k, v in pause.items()) for pause in row["paused_scopes"])
                or is_paused(project, key, row["version"], scope)
                or catalog_paused(project, key, row["version"], scope)):
            raise ValueError(f"{key}: paused")
        pending.extend(row["dependencies"])
    return rows[asset_id]


def applicable(project, asset_id, scope):
    return _available(project, discover(project), asset_id, scope)


SELECTION_SCOPE = ("project_group", "product", "system", "module_path", "function", "checkpoint",
                   "environment", "risk_level", "case_id", "step_id")


def catalog_paused(project, key, version, scope):
    from .asset_revision import AssetCatalog
    return AssetCatalog(project).paused(key, version, scope)


def check_selected_pauses(project, decision, rows, scope):
    """Check the pinned root and its full selected dependency closure immediately before use."""
    from ui_test_core.reuse_outcome import ReuseFailure
    for key in (decision["asset_id"], *decision["dependencies"]):
        row = rows[key]
        if (is_paused(project, key, row["version"], scope)
                or catalog_paused(project, key, row["version"], scope)
                or any(all(scope.get(k) == v for k, v in restriction.items())
                       for restriction in row["paused_scopes"])):
            raise ReuseFailure("unknown", f'{scope["step_id"]}: {key} version {row["version"]} paused')


def select_asset(project, capability, scope, authorization, *, binding=None, pinned_rows=None):
    """Resolve one source step against its current grant. Never execute a candidate."""
    decision = dict(scope=dict(scope), step_id=scope.get("step_id"), capability=capability,
                    binding=binding, status="blocked", skipped={})
    if (not all(k in scope and (scope[k] or k == "checkpoint") for k in SELECTION_SCOPE)
            or authorization.get("approved") is not True or authorization.get("scope") != scope):
        return dict(decision, reason="case_scope_not_authorized")
    effects = authorization.get("effects", [])
    facts = authorization.get("facts", [])
    if not all(isinstance(values, (list, tuple)) and all(isinstance(item, str) and item for item in values)
               for values in (effects, facts)):
        return dict(decision, reason="invalid_case_grant")
    rows = discover(project) if pinned_rows is None else pinned_rows
    eligible = {"dedicated": [], "shared": []}

    def check_policy(key, ancestors):
        if key in ancestors:
            raise ValueError(f"{key}: cyclic dependency")
        asset = rows[key]
        if scope["step_id"] not in asset["steps"]:
            raise ValueError(f"{key}: step outside enabled scope")
        if asset.get("owner") != {k: scope[k] for k in ("project_group", "product")}:
            raise ValueError(f"{key}: different project")
        if not asset.get("conditions", {}).get("environment"):
            raise ValueError(f"{key}: environment unspecified")
        effect = asset.get("side_effects")
        if not effect or effect == "unknown" or effect not in effects:
            raise ValueError(f"{key}: effect not authorized")
        if not set(asset.get("prerequisites", ())).issubset(facts):
            raise ValueError(f"{key}: prerequisites not met")
        for dependency in asset["dependencies"]:
            check_policy(dependency, ancestors | {key})

    for key, asset in rows.items():
        if asset.get("capability", key) != capability and key != binding:
            continue
        if binding is not None and key != binding:
            decision["skipped"][key] = "source binding takes precedence"
            continue
        try:
            if asset.get("capability", key) != capability:
                raise ValueError(f"{key}: capability mismatch")
            _available(project, rows, key, scope)
            check_policy(key, set())
            tier = asset.get("sharing", "dedicated")
            if tier not in eligible:
                raise ValueError(f"{key}: unrecognized sharing policy")
            eligible[tier].append(key)
        except ValueError as error:
            decision["skipped"][key] = str(error)

    if binding is not None and binding not in rows:
        decision["skipped"][binding] = "missing declaration"
    for tier, candidates in eligible.items():
        if not candidates:
            continue
        if tier == "dedicated":
            decision["skipped"].update(dict.fromkeys(eligible["shared"], "lower priority"))
        if len(candidates) > 1:
            return dict(decision, status="conflict", conflicts=sorted(candidates), reason="same_priority")
        key = candidates[0]
        dependencies = {}
        pending = list(rows[key]["dependencies"])
        while pending:
            dep = pending.pop()
            if dep not in dependencies:
                dependencies[dep] = {k: rows[dep][k] for k in ("version", "sha256", "recovery_source", "symbol")}
                pending.extend(rows[dep]["dependencies"])
        return dict(decision, status="selected", asset_id=key, asset=rows[key], dependencies=dependencies,
                    tier="explicit" if binding is not None else tier)
    if binding is not None:
        return dict(decision, reason="hard_binding_unavailable")
    if any(reason.endswith(": paused") for reason in decision["skipped"].values()):
        return dict(decision, reason="paused")
    exploration_effect = authorization.get("exploration_effect")
    may_explore = authorization.get("explore") is True and exploration_effect not in (None, "unknown") and exploration_effect in effects
    return dict(decision, status="exploration_allowed" if may_explore else "blocked",
                reason="no_applicable_asset")


def trace_run(run_root):
    """Walk the committed result to step evidence without executing or importing it."""
    root = Path(run_root).resolve()
    final = root / "finalization"
    commit = json.loads((final / "finalization-commit.json").read_text(encoding="utf-8"))
    result = json.loads(inside(final, commit["run_result_ref"]).read_text(encoding="utf-8"))
    from ui_test_core.case_contracts import canonical_hash
    signed = {key: value for key, value in result.items() if key != "run_result_hash"}
    if (result["run_id"] != commit["run_id"] or result["run_result_hash"] != commit["run_result_hash"]
            or canonical_hash(signed) != commit["run_result_hash"]):
        raise ValueError("result does not belong to commit")
    uses = []
    for step in result["step_results"]:
        for ref in step.get("evidence_refs", []):
            if not ref.endswith(".json"):
                continue
            detail = json.loads(inside(root, ref).read_text(encoding="utf-8"))
            if isinstance(detail, dict) and "asset_id" in detail:
                if (any(detail.get(key) != result[key] for key in ("run_id", "case_id", "attempt_ref"))
                        or detail["step_id"] != step["step_id"]):
                    raise ValueError("asset evidence identity mismatch")
                uses.append(detail)
    return uses
