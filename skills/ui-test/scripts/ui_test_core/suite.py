"""Resolve capability implementations from the same installation as this runtime."""
from importlib import import_module, util
import json
import os
from pathlib import Path
import sys
from types import ModuleType


class Suite:
    def __init__(self, root):
        self.root = root
        self.catalog = json.loads((root / "references/capabilities.json").read_text(encoding="utf8"))
        if self.catalog.get("schema_version") != 1:
            raise ValueError("E_SUITE_CATALOG_VERSION")
        self.layout = json.loads((root / "references/suite-layout.json").read_text(encoding="utf8"))

    def canonical_name(self, name):
        matches = [entry["name"] for entry in self.catalog["entries"]
                   if name == entry["name"] or name in entry.get("aliases", [])]
        if len(matches) > 1:
            raise ValueError("E_SUITE_CAPABILITY_AMBIGUOUS: " + ", ".join(matches))
        if not matches:
            raise ValueError("E_SUITE_CAPABILITY_UNKNOWN: " + name)
        return matches[0]

    def skill_path(self, name):
        name = self.canonical_name(name)
        path = (self.root / self.layout.get(name, "../" + name)).resolve()
        if not (path / "SKILL.md").is_file():
            raise ValueError("E_SUITE_CAPABILITY_MISSING: " + str(path))
        return path

    def load_package(self, name):
        name = self.canonical_name(name)
        scripts = self.skill_path(name) / "scripts"
        key = "ui_test_core.capability_" + name.replace("-", "_")
        if key in sys.modules:
            package = sys.modules[key]
            if Path(package.__path__[0]).resolve() != scripts:
                raise ValueError("E_SUITE_PACKAGE_CONFLICT: " + name)
            return package
        if not scripts.is_dir():
            raise ValueError("E_SUITE_PACKAGE_MISSING: " + name)
        init = scripts / "__init__.py"
        if not init.is_file():
            package = ModuleType(key)
            package.__path__ = [str(scripts)]
            package.__package__ = key
            sys.modules[key] = package
            return package
        spec = util.spec_from_file_location(key, init, submodule_search_locations=[str(scripts)])
        package = util.module_from_spec(spec)
        sys.modules[key] = package
        try:
            spec.loader.exec_module(package)
        except BaseException:
            del sys.modules[key]
            raise
        return package


def selected_suite(root=None, *, _loading_bridge=None):
    current = Path(__file__).resolve().parents[2]
    # Historical pytest projects import scripts.ui_test_core through the main Skill.
    # Bind the already-loaded modules before the report owner imports canonical names.
    if __package__ == "scripts.ui_test_core":
        for alias, module in list(sys.modules.items()):
            if alias == _loading_bridge:  # The forwarding module is still being imported.
                continue
            if alias == __package__ or alias.startswith(__package__ + "."):
                canonical = alias.removeprefix("scripts.")
                existing = sys.modules.setdefault(canonical, module)
                if Path(existing.__file__).resolve() != Path(module.__file__).resolve():
                    raise ValueError("E_SUITE_RUNTIME_CONFLICT: " + canonical)
    if root is None and os.environ.get("UI_TEST_SUITE"):
        choices = list(dict.fromkeys(Path(path).resolve() for path in os.environ["UI_TEST_SUITE"].split(os.pathsep) if path))
        if len(choices) != 1:
            raise ValueError("E_SUITE_AMBIGUOUS: " + ", ".join(map(str, choices)))
        root = choices[0]
    if root is not None and Path(root).resolve() != current:
        raise ValueError(f"E_SUITE_CONFLICT: loaded {current}, requested {root}")
    return Suite(current)

def owner_module(skill, name, caller):
    """Resolve historical imports and retain one module identity across both core namespaces."""
    package = selected_suite(_loading_bridge=caller).load_package(skill)
    target = import_module(package.__name__ + "." + name)
    canonical = "ui_test_core." + name
    existing = sys.modules.get(canonical)
    if existing is not None and existing not in (sys.modules.get(caller), target):
        raise ValueError("E_SUITE_RUNTIME_CONFLICT: " + canonical)
    if caller != "__main__":
        sys.modules[caller] = sys.modules[canonical] = target
    return target
