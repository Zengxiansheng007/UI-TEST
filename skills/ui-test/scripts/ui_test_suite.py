"""Run a command using the explicitly selected UI-Test installation."""
import argparse
import json
import os
from pathlib import Path
import sys


def choose_root(explicit=None):
    locations = [explicit] if explicit else os.environ.get("UI_TEST_SUITE", "").split(os.pathsep)
    roots = list(dict.fromkeys(Path(p).resolve() for p in locations if p)) or [Path(__file__).resolve().parents[1]]
    if len(roots) != 1:
        raise ValueError("E_SUITE_AMBIGUOUS: select --suite from " + ", ".join(map(str, roots)))
    root = roots[0]
    if not (root / "references/capabilities.json").is_file() or not (root / "scripts/ui_test_core/__init__.py").is_file():
        raise ValueError(f"E_SUITE_MISSING: {root}")
    return root


def activate(explicit=None):
    root = choose_root(explicit)
    loaded = sys.modules.get("ui_test_core")
    if loaded is not None and Path(loaded.__file__).resolve().parents[2] != root:
        raise ValueError("E_SUITE_CONFLICT: start a fresh process for " + str(root))
    scripts = str(root / "scripts")
    if scripts not in sys.path[:1]:
        sys.path.insert(0, scripts)
    return root


def main(argv=None, *, quiet=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", help="selected main ui-test Skill directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("route").add_argument("packet", type=Path)
    commands.add_parser("catalog")
    commands.add_parser("resolve").add_argument("name")
    for capability in ("assets", "experience"):
        commands.add_parser(capability).add_argument("--input", type=Path, required=True)
    checkpoint = commands.add_parser("checkpoint-schema", aliases=["ui-test-checkpoint-schema"])
    checkpoint.add_argument("arguments", nargs=argparse.REMAINDER)
    handoff = commands.add_parser("a2a-handoff", aliases=["ui-test-a2a-handoff"])
    handoff.add_argument("source", type=Path)
    handoff.add_argument("--review-notes", type=Path)
    destination = handoff.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument("--project", type=Path)
    handoff.add_argument("--stage", choices=("midscene", "playwright"))
    handoff.add_argument("--stage-run-id")
    report = commands.add_parser("execution-report", aliases=["ui-test-execution-report"])
    source = report.add_mutually_exclusive_group(required=True)
    source.add_argument("--observations", type=Path)
    source.add_argument("--session", type=Path)
    report.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = activate(args.suite)
        os.environ["UI_TEST_SUITE"] = str(root)
        from ui_test_core.suite import selected_suite
        suite = selected_suite(root)
        if args.command == "catalog":
            result = suite.catalog
        elif args.command == "route":
            from ui_test_core.routing import select_packet
            result = select_packet(json.loads(args.packet.read_text(encoding="utf-8-sig")))
            if not result["ok"]:
                parser.exit(2, json.dumps(result, ensure_ascii=True) + "\n")
        elif args.command == "resolve":
            result = dict(skill=str(suite.skill_path(args.name)), core_scripts=str(root / "scripts"))
        elif args.command in ("assets", "experience"):
            owner = suite.load_package(args.command)
            request = json.loads(args.input.read_text(encoding="utf-8-sig"))
            result = owner.query(**request)
        elif args.command in ("checkpoint-schema", "ui-test-checkpoint-schema"):
            return suite.load_package("checkpoint-schema").main(args.arguments)
        elif args.command in ("a2a-handoff", "ui-test-a2a-handoff"):
            result = suite.load_package("a2a-handoff").deliver(args)
        else:
            owner = suite.load_package("execution-report")
            result = owner.rebuild(args.observations, args.session, args.output)
        if not quiet:
            print(json.dumps(result, ensure_ascii=True, sort_keys=args.command in ('assets', 'experience')))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
