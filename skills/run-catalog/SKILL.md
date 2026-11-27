---
name: run-catalog
description: Register or replay UI test stages and attempts and retrieve the script or exploration plan used at that time. Use when given a project and original stage record, stage, case, branch or attempt ID.
---

# 运行登记

给出项目根目录和查询条件。使用所选主 Skill 的套件目录解析本入口，将该主 Skill 的 scripts 目录加入 PYTHONPATH。用 Python 执行本入口的[运行查询命令](scripts/project_catalog.py)。

- 只给项目目录时，重放该项目运行目录中的 start.json、事件与 stage.json，生成 runs.sqlite3 和可离线打开的 index.html。生产入口继续通过阶段开始、尝试登记和阶段封存保存原件。
- 给出原件时，在项目目录后加 `--original "运行/.../stage.json"`。接受项目内准确的 start.json 或 stage.json。按标识检索使用 `--stage`、`--case`、`--branch`、`--attempt`，可组合限定。
- 逐次返回项目相对路径、历史版本、绑定的脚本或计划、依赖和阶段报告。多个匹配阶段列为候选供选择，找不到标识或原件则返回对应状态及缺项。对照哈希后按历史绑定打开文件。只给口头描述时先取得准确项目和标识。
- 项目旧命令 project_catalog.py PROJECT 可继续刷新两个索引。交付结果后返回请求方。

## 独立登记

在已选定套件的 Python 进程中，以 `owner = selected_suite().load_package("run-catalog")` 取登记入口。调用 `owner.stage_started(project, stage, stage_id, started_at, owners)` 保留原阶段和用例分支身份；每次实际尝试调用 `owner.record_attempt(project, stage, stage_id, case_owner, attempt)`。以上 project 传入绝对 Path，owners 的每项含 case_id、branch_id，attempt 含当次 attempt_ref、status 及已有版本绑定和证据。已有完整封存记录时调用 `owner.register_stage(project, record)`。查询已有记录使用上一节命令。

## Validation

比对阶段原件的阶段、用例、尝试与返回身份。以同一项目重复刷新，核对 SQLite 的 run_attempts 及离线 HTML。历史版本依绑定的 entry 与 sha256 判定。源码路径当前可以已换版。

## Safety

读写范围为所选项目的本地索引与登记文件，查询无需页面操作、模型或网络。
