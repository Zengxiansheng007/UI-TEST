"""Retain the project sources selected when an attempt actually starts."""
import ast
import sys
from pathlib import Path

from .artifact_layout import ProjectLayout, checked_path
from .asset_revision import digest, encoded, replace
from .file_lock import exclusive_file_lock
from .path_planner import validate_existing_path_containment
from .release_verifier import verify_release


def source_ref(root, path):
    validate_existing_path_containment(root, path)
    relative = path.resolve().relative_to(root)
    if any(part.casefold() in {"_private", ".git", ".env", ".codex", "node_modules"} for part in relative.parts):
        raise ValueError("E_VERSION_PRIVATE_SOURCE")
    return relative.as_posix()


def snapshot(root, source, data, suffix):
    sha = digest(data)
    path = checked_path(root / "版本" / (sha[:32] + suffix))
    validate_existing_path_containment(root, path)
    lock = path.parent / ".snapshot.lock"
    validate_existing_path_containment(root, lock)
    with exclusive_file_lock(lock):
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError("E_VERSION_BLOB_CONFLICT")
        else:
            replace(path, data)
    return dict(source=source, entry=path.relative_to(root).as_posix(), sha256=sha)


def make_binding(entry, node, deps, release=None):
    files = sorted(deps, key=lambda row: row["source"])
    identity = [(row["source"], row["sha256"]) for row in [entry, *files]]
    version = release if release and not files else "sha256:" + digest(encoded([release, identity]))
    return dict(**entry, node_id=node, dependencies=files, version=version, release=release)


def python_imports(root, source, data):
    for node in ast.walk(ast.parse(data)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module] if node.module else []
            names.extend(".".join(filter(None, (node.module, alias.name))) for alias in node.names)
        else:
            continue
        for name in names:
            loaded = sys.modules.get(name)
            loaded_file = getattr(loaded, "__file__", None)
            if loaded_file and not getattr(node, "level", 0):
                path = Path(loaded_file).resolve()
                if path.suffix == ".py" and path.is_relative_to(root):
                    yield path
                continue
            bases = [source.parent, root]
            level = getattr(node, "level", 0)
            if level:
                bases = [source.parents[level - 1]] if level <= len(source.parents) else []
            for base in bases:
                target = base.joinpath(*name.split("."))
                choices = [target.with_suffix(".py"), target / "__init__.py"]
                file = next((p for p in choices if p.is_file() and p.resolve().is_relative_to(root)), None)
                if file:
                    yield file
                    for parent in file.parents:
                        if parent == base or not parent.is_relative_to(base):
                            break
                        if (parent / "__init__.py").is_file():
                            yield parent / "__init__.py"
                    break


def verified_release(root, path, data, owner):
    candidates = [path.parent] if path.parent.parent.name == "releases" else []
    if owner:
        folder = ProjectLayout(root).case_dir(*owner) / "releases"
        candidates.extend(sorted(folder.glob("*")))
    for directory in candidates:
        validate_existing_path_containment(root, directory)
        artifact = directory / "playwright-test.py"
        validate_existing_path_containment(root, artifact)
        if not artifact.is_file() or artifact.read_bytes() != data:
            continue
        state = verify_release(directory)
        if (state["release_integrity"] != "valid" or directory.name != state["build_fingerprint"].removeprefix("sha256:")
                or (owner and tuple(owner) != (state["case_id"], state["branch_id"]))):
            continue
        return artifact, state["build_fingerprint"]
    return None, None


def bind_python(root, path, node, known_files, *, owner=None, runner_digest=None):
    root, path = Path(root).resolve(), Path(path).resolve()
    source = source_ref(root, path)
    data = path.read_bytes()
    if runner_digest and runner_digest != "sha256:" + digest(data):
        raise ValueError("E_VERSION_RUNNER_CHANGED")
    release_path, release = verified_release(root, path, data, owner)
    entry = (dict(source=source, entry=source_ref(root, release_path), sha256=digest(data))
             if release else snapshot(root, source, data, ".py"))
    seen, deps = {path}, []
    pending = [*known_files, *python_imports(root, path, data)]
    while pending:
        file = Path(pending.pop()).resolve()
        if file in seen:
            continue
        seen.add(file)
        relative = source_ref(root, file)
        raw = file.read_bytes()
        deps.append(snapshot(root, relative, raw, ".py"))
        pending.extend(python_imports(root, file, raw))
    return make_binding(entry, node, deps, release)


def bind_exploration(root, plan):
    root = Path(root).resolve()
    entry = snapshot(root, "selected-plan.json", encoded(plan["selected_plan"]), ".json")
    deps = []
    for value in sorted(set(plan.get("dependencies", []))):
        path = root / value
        relative = source_ref(root, path)
        if path.suffix.lower() not in {".js", ".mjs", ".cjs", ".json", ".ts"}:
            raise ValueError("E_VERSION_DEPENDENCY_TYPE")
        deps.append(snapshot(root, relative, path.read_bytes(), path.suffix.lower()))
    return make_binding(entry, plan["node_id"], deps)

