---
name: playwright-run
description: 执行选定的正式 Playwright pytest 节点，返回本次 V5 断言、步骤证据及正式阶段报告。Use when an approved project has qualified scripts and selected formal nodes.
---

# 正式 Playwright 执行

核对所选套件、项目、环境、脚本版本、当前前置、节点清单及授权。缺项时列出所缺材料并返回。只办理本次正式阶段。

在业务项目根目录设置 `UI_TEST_SUITE` 为所选主 Skill 的绝对目录，然后运行以下命令。重复 `--node` 可指定多个节点。任务路径须为绝对路径，批次号绑定完整选择。

```text
python <playwright-run>/scripts/run.py --task-ref <task.json> --batch-ref <batch> --node <file.py::test_case>
```

## Safety and authorization

Codex 默认串行。只有用户明确授权了本任务、本批次和完整节点集才传入 `--parallel-intent <intent.json>`。人工可在项目原 pytest 或 PyCharm 入口按自身需要选择并发。兼容项目保留原 conftest 插件声明。以现有阶段预算约束写入，结果未知时停止并沿同一任务记录核实，保留尝试及回执。凭据沿已配置引用加载。请求证据仅监听 UI 自然触发的请求。

## Validation and delivery

正式只读脚本须提供 `r0(formal_result=True)` 和事务候选钩子。沿本次回执读取 V5 的断言、步骤和证据，沿运行登记查实际脚本。将控制器输出的单份阶段报告、批次状态、缺失项及未执行原因交还调用方。遇到暂停退出码 75 时返回任务、批次和未确认原因。

正式 R2 运行在节点参数后追加 `-- --ui-r2-approved --ui-write-budget <项目内预算文件> --ui-write-budget-sha256 <已批准摘要>`。按`ui-test.formal-write-budget.v1` 格式核对批次、节点、用例、分支与阶段。操作前消费当前阶段的一次性许可。发生中断后保留原领取记录。
