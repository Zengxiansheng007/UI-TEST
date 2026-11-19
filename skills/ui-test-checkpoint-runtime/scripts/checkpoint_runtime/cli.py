from __future__ import annotations

import argparse
import uuid
import json
import os
from pathlib import Path

from .registry import CheckpointRegistry
from .models import RuntimeTarget
from .planner import RecoveryPlanner
from .playwright_executor import PlaywrightExecutor
from .reporter import EvidenceReporter
from .policy import assert_auth_reportable_boundary
from .context import capture_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Checkpoint Runtime v1 dry-run planner")
    parser.add_argument("--root", required=True, help="Runtime asset root")
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--module-id", required=True)
    parser.add_argument("--button-id")
    parser.add_argument("--environment-alias")
    parser.add_argument("--project-group", default="public-pilot")
    parser.add_argument("--product", default="public-ui")
    parser.add_argument("--function", default="module-entry")
    parser.add_argument("--checkpoint", default="CP3-module-entry")
    parser.add_argument("--risk-level", default="R0", choices=["R0", "R1"])
    parser.add_argument("--ready-packet", help="Current Packet 3.0 for visible live readiness")
    parser.add_argument("--report", required=True, help="Path to write runtime-report.json")
    parser.add_argument("--run-id", help="Stable run id for traceability")
    parser.add_argument("--session-id", help="Current browser session id; never reused across independent sessions")
    parser.add_argument("--correlation-id", help="Stable cross-session correlation id")
    parser.add_argument("--mode", choices=["dry-run", "live-public"], default="dry-run")
    parser.add_argument("--node-path", help="Node executable path for live-public mode")
    parser.add_argument("--playwright-module", help="Optional Playwright module path, e.g. D:\\midscene\\node_modules\\playwright")
    parser.add_argument("--evidence-dir", help="Directory for browser evidence in live-public mode")
    parser.add_argument("--proxy-server", help="Optional proxy for public live tests, e.g. http://127.0.0.1:7890")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = RuntimeTarget(
        system_id=args.system_id,
        module_id=args.module_id,
        function_button_id=args.button_id,
        environment_alias=args.environment_alias,
        project_group=args.project_group,
        product=args.product,
        function=args.function,
        checkpoint=args.checkpoint,
        risk_level=args.risk_level,
    )
    registry = CheckpointRegistry(Path(args.root))
    module_manifest = registry.load_module_manifest(target)
    checkpoint_index = registry.load_checkpoint_index(target)
    auth_ref = registry.load_auth_ref(target, module_manifest)
    assert_auth_reportable_boundary(auth_ref)
    run_id = args.run_id or f"run-{uuid.uuid4().hex[:12]}"
    session_id = args.session_id or f"session-{uuid.uuid4().hex[:12]}"
    correlation_id = args.correlation_id or run_id
    plan = RecoveryPlanner().build_plan(target, module_manifest, checkpoint_index, auth_ref, run_id, correlation_id)
    execution_result = None
    if args.mode == "live-public" and not plan.blocked and args.button_id:
        if not args.node_path:
            raise SystemExit("--node-path is required for live-public button recovery")
        evidence_dir = Path(args.evidence_dir) if args.evidence_dir else Path(args.report).parent / run_id
        executor = PlaywrightExecutor(runner_path=Path(__file__).with_name("playwright_runner.cjs"),
                                      node_path=Path(args.node_path),
                                      playwright_module=Path(args.playwright_module) if args.playwright_module else None)
        execution_result = executor.execute(root=Path(args.root), plan=plan, module_manifest=module_manifest,
                                            auth_ref=auth_ref, out_dir=evidence_dir, proxy_server=args.proxy_server)
    elif args.mode == "live-public" and not plan.blocked:
        from playwright.sync_api import sync_playwright
        if not args.ready_packet:
            raise SystemExit("--ready-packet is required for live-public")
        packet = json.loads(Path(args.ready_packet).read_text(encoding="utf-8"))
        config = dict(module_manifest.get("module_ready", {}), target_url=module_manifest["base_url"], module_id=target.module_id)
        scope = packet.get("scope", {})
        expected = dict(system=target.system_id, project_group=target.project_group, product=target.product,
                        function=target.function, checkpoint=target.checkpoint, environment=target.environment_alias or "public",
                        risk_level={"R0":"r0-read-only","R1":"r1-read-only-authenticated"}[target.risk_level])
        if (any(scope.get(k) != v for k, v in expected.items()) or target.module_id not in scope.get("module_path", [])
                or packet.get("run", {}).get("run_id") != run_id or args.button_id):
            raise SystemExit("E_MODULE_READY_TARGET_MISMATCH")
        try:
            with sync_playwright() as engine:
                browser = engine.chromium.launch(headless=False, channel=os.environ.get("UI_TEST_BROWSER_CHANNEL"))
                page = browser.new_page()
                ready = capture_context(page, packet=packet, config=config, session_id=session_id,
                                        enter=lambda active: active.goto(config["target_url"], wait_until="load"))
                execution_result = {"result": "passed", "module_ready_context": ready, "artifacts": []}
                browser.close()
        except ValueError as exc:
            execution_result = {"result": "failed", "failure_attribution": {"layer":"policy","detail":str(exc)}}
    report = EvidenceReporter().build_report(plan, auth_ref, mode=args.mode, execution_result=execution_result)
    EvidenceReporter().write_report(Path(args.report), report)
    if plan.blocked:
        return 2
    if execution_result and execution_result.get("result") != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
