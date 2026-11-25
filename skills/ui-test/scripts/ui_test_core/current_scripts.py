"""Resolve current case entries from explicit declarations and verified active releases."""
import ast
from collections import defaultdict
from pathlib import Path
import tokenize

from .artifact_layout import ProjectLayout
from .path_planner import validate_existing_path_containment
from .strict_json import load_strict_json


def case_row(case, branch, name, source):
    return dict(case_id=case, branch_id=branch, display_name=name, source=source,
                status="pending", reason="缺少可核实的生效入口", entry=None, node_id=None)


def formal_nodes(path):
    with tokenize.open(path) as stream:
        module = ast.parse(stream.read())
    nodes = {}
    def visit(body, prefix):
        for item in body:
            if isinstance(item, ast.ClassDef):
                visit(item.body, prefix + item.name + "::")
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                nodes[prefix + item.name] = item
    visit(module.body, "")
    return nodes


def hand_entries(root):
    from .artifact_inventory import private
    config = root / "current-cases.json"
    validate_existing_path_containment(root, config)
    if not config.is_file():
        return
    items = load_strict_json(config)["cases"]
    if not isinstance(items, list):
        raise ValueError("E_CURRENT_CASES_CONFIG")
    for item in items:
        values = [item.get(k) for k in ("case_id","branch_id","display_name","node_id")]
        if not all(isinstance(value,str) and value.strip() for value in values):
            raise ValueError("E_CURRENT_CASES_CONFIG")
        case, branch, name, node = values
        row = case_row(case, branch, name, config.name)
        file, _, selector = node.partition("::")
        rel = Path(file)
        if (not rel.parts or rel.anchor or ".." in rel.parts or ":" in file or private(rel)
                or rel.suffix.lower() != ".py" or not selector):
            row["reason"] = "脚本或测试节点超出声明范围"
        else:
            path = root / rel
            try:
                validate_existing_path_containment(root, path)
                function = formal_nodes(path).get(selector)
                if function is None:
                    row["reason"] = "声明的测试节点不存在"
                else:
                    for decorator in function.decorator_list:
                        if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                                and isinstance(decorator.func.value, ast.Attribute) and decorator.func.value.attr == "mark"):
                            marker = decorator.func.attr
                            if marker in ("case_id","branch_id") and decorator.args and isinstance(decorator.args[0],ast.Constant):
                                if decorator.args[0].value != row[marker]:
                                    raise ValueError("声明与节点的用例或分支不一致")
                    row.update(status="current", reason="项目声明", entry=rel.as_posix(),node_id=node)
            except FileNotFoundError:
                row.update(status="missing",reason="当前脚本缺件")
            except (OSError, SyntaxError, UnicodeError, ValueError):
                row["reason"] = "脚本、测试节点或用例归属无法核实"
        yield row


def current_scripts(root, legacy):
    cases = {}
    by_owner = defaultdict(list)
    layout = ProjectLayout(root)
    for source in sorted((root/"用例").glob("*/case.json")):
        validate_existing_path_containment(root,source)
        data = load_strict_json(source)
        key = (data["case_id"],data["branch_id"])
        if source.parent != layout.case_dir(*key):
            raise ValueError("E_CURRENT_CASE_IDENTITY")
        cases[key] = case_row(*key,data["display_name"],source.relative_to(root).as_posix())
    for item in legacy:
        if item["kind"] != "script" or item["status"] != "current":
            continue
        key = (item["case_id"],item["branch_id"])
        row = case_row(*key,cases[key]["display_name"] if key in cases else key[0],item["source"])
        row.update(status="current", reason="已核验生效发布",entry=item["path"])
        try:
            nodes = formal_nodes(root/item["path"])
            if len(nodes)==1:
                row["node_id"] = item["path"] + "::" + next(iter(nodes))
        except (OSError, UnicodeError, SyntaxError):
            row.update(status="pending",entry=None,reason="已发布脚本无法读取")
        by_owner[key].append(row)
    for row in hand_entries(root):
        key = (row["case_id"],row["branch_id"])
        by_owner[key].append(row)
    for key, options in by_owner.items():
        row = options[0].copy()
        if len(options)>1:
            row.update(status="pending", reason="同一用例分支有多份当前入口声明",entry=None,node_id=None)
        cases[key] = row
    return [cases[k] for k in sorted(cases)]
