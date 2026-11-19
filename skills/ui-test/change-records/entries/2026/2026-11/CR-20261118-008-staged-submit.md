# CR-20261118-008 — 分阶段提交

| Field | Value |
| --- | --- |
| Change ID | CR-20261118-008 |
| Status | applied |

## Summary

支持已授权的分阶段可见 UI 提交。

## Context And Problem

旧指令一律禁止第二次提交；已登记未知的阶段可以再次登记成功。

## Sections Changed

stage_write_budget.py 锁定已登记结果。test_stage_write_budget.py 验证未知状态无法覆盖。specified-runner 的项目配置、用例和 finalization 回调复用 controlled_ui_page.py，按阶段核对提交、响应和页面。

## Decision And Alternatives

复用既有授权、阶段预算、一次性许可与 V5 结果格式。

## Impact Analysis

默认运行保持一次提交。两阶段用例要求每阶段业务前后置断言及已核实的前序结果。

## Validation Evidence

本地可见 Chrome 两条实际入口的 V5 总数分别为 1 和 2。阶段预算回归 26 项通过。证据位于 .scratch/t07-evidence.json。

## Safety And Privacy

测试数据由回环受控页面产生，浏览器点击触发写操作。

## Risks And Follow-up

整套集成验收归属 T09。

