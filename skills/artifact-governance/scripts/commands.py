"""Inspect and govern a local UI-Test project."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from .inventory_report import publish_inventory
from .retention_preview import publish_preview
from .stage_archive import approve, archive, verify_archive
from .stage_release import release
from .archive_history import restore_stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action",required=True)
    inventory = actions.add_parser("inventory",help="盘点项目生成物、已知使用方及步骤")
    inventory.add_argument("project",type=Path)
    preview = actions.add_parser("preview",help="按当前保留策略生成阶段治理待审清单")
    preview.add_argument("project",type=Path)
    preview.add_argument("--request-id", help="可复用的命名空间请求标识，例如 schedule:2026-11")
    enable = actions.add_parser("schedule-enable",help="当前登录用户启用 Windows 定时预演")
    enable.add_argument("project",type=Path)
    enable.add_argument("--test-in-minutes",type=int,help="在隔离项目创建一次性测试触发")
    due = actions.add_parser("scheduled-preview",help="登录或周期触发后检查到期预演")
    due.add_argument("project",type=Path)
    due.add_argument("--first-due",type=datetime.fromisoformat,required=True)
    approval = actions.add_parser("approve", help="批准清单中的具体阶段、目标和拟释放范围")
    approval.add_argument("project",type=Path)
    approval.add_argument("preview_id")
    approval.add_argument("stage_ids",nargs="+")
    pack = actions.add_parser("archive", help="按批准批次复制并验证各阶段归档")
    pack.add_argument("project",type=Path)
    pack.add_argument("approval_id")
    dispose = actions.add_parser("release", help="复核同一批批准、归档与使用方后逐项释放工作副本")
    dispose.add_argument("project",type=Path)
    dispose.add_argument("approval_id")
    verify = actions.add_parser("verify-archive", help="只使用归档内的文件核验并打开阅读入口")
    verify.add_argument("directory", type=Path)
    restore = actions.add_parser("restore", help="将选定历史阶段恢复到项目和归档外的短目录")
    restore.add_argument("project", type=Path)
    restore.add_argument("stage_id")
    restore.add_argument("destination", type=Path)
    restore.add_argument("--manifest-sha256", help="有多个归档版本时选择清单摘要")
    args = parser.parse_args()
    if args.action == "schedule-enable":
        from .preview_schedule import enable_schedule
        print(json.dumps(enable_schedule(args.project,trial_minutes=args.test_in_minutes),ensure_ascii=False))
    elif args.action == "scheduled-preview":
        from .preview_schedule import due_preview
        print(due_preview(args.project,args.first_due) or "尚未到期")
    elif args.action == "approve":
        print(approve(args.project,args.preview_id,args.stage_ids))
    elif args.action in {"archive","release"}:
        result = (archive if args.action == "archive" else release)(args.project,args.approval_id)
        print(result)
        expected = "verified" if args.action == "archive" else "released"
        if any(row["status"] != expected for row in json.loads(result.read_bytes())["stages"].values()):
            return 2
    elif args.action == "verify-archive":
        verify_archive(args.directory)
        print(args.directory.resolve()/"index.html")
    elif args.action == "restore":
        print(restore_stage(args.project,args.stage_id,args.destination,args.manifest_sha256))
    elif args.action == "preview":
        print(publish_preview(args.project,request_id=args.request_id))
    else:
        print(publish_inventory(args.project))


if __name__=="__main__":
    raise SystemExit(main())
