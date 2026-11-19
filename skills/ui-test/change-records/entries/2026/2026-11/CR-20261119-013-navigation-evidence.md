# CR-20261119-013 · TodoMVC 源用例导航证据

| Field | Value |
| --- | --- |
| Status | validated |
| Target Skill | ui-test |
| Issue | #13 |

## Summary

项目正常 pytest 入口按源用例 OPEN 绑定调用 TodoPage.open 并将本次导航明细关联到 V5。

## Context And Problem

旧样例直接调用页面方法，接手者无法从一次结果区分选中的绑定、实际调用的方法及版本。

## Sections Changed

scripts-and-validation，references-and-assets。项目样例在 examples/todomvc。

## Decision And Alternatives

沿用受控运行时和源断言，从编译步骤取得 binding_ref，再验证导航声明、方法名和文件摘要。

## Detailed Change

TodoPage.open 在自身入口报告当前页面。原断言通过后写入可见状态、运行 ID 和尝试引用。版本 1 的恢复文件位于 versions/flow.open-todomvc/1/todomvc_page.py。

## Impact Analysis

V5 的 OPEN 同时引用截图和本次调用明细。执行仍由项目 fixture 创建独立浏览器上下文。

## Safety And Privacy

浏览器仅访问公开 TodoMVC。新增和完成各消费当前运行的一次阶段许可。

## Risks And Follow-up

该样例依赖本机已经准备好的正式源用例和 Chromium。多资产发现及冲突选择由后续工单覆盖。

## Validation Evidence

在项目目录执行以下命令，RUN_ID 使用新的唯一值。仅在已授权公开练习环境运行。操作按原两阶段预算分别新增和勾选一条本地待办。

    python -B -m pytest regression-runners/test_todo_p0_002.py --headed --browser chromium --ui-run-id RUN_ID --ui-r2-approved --ui-execution-origin codex-cli -q -p no:cacheprovider

2026-11-19 实跑 REUSE13-20261119-004，退出码 0，1 passed。既有生成器的 p0 mark 有一条未登记警告。读取 asset-paths.json 内 TODO-P0-002 的 branch_root 下 runs/REUSE13-20261119-004/finalization/finalization-commit.json，通过 run_result_ref 回读已提交 V5。OPEN 引用 reports/navigation-use.json，当前输入框可见且列表为空。其后 FILL、ADD、READY-COMPLETE、COMPLETE 均通过。明细关联同次运行、用例、源步骤及 attempt_ref。早期运行 001 在收集阶段遇到旧 hook，002 在导航前遇到源步骤字段不匹配，003 业务断言通过但审批边界摘要与现行终结契约不符。004 使用新上下文和新运行号。

