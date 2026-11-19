# CR-20261119-017 · 失败时保存复用与写入证据

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Issue | #17 |

## Summary

TodoMVC 正式节点记录入口选择、跳过原因、已派发次数与分阶段结果。

## Context And Problem

业务写入后出现异常时，原适配器可能无法提供 V5 候选，也无法区分已选和已进入。

## Sections Changed

scripts-and-validation 与 examples/todomvc。

## Decision And Alternatives

沿用正式 pytest 事务和预算。先独占运行标记，再在 UI 动作之前保存本次已用预算。

## Detailed Change

确认资产故障按项目、版本、环境、用例和步骤保存暂停决定。未知原因停止依赖步骤。普通结果单独提供本次复用是否证实。

## Impact Analysis

V5 保留业务断言和预算，源节点继续使用原有页面断言。失败时继续沿同一事务完成回执。

## Safety And Privacy

项目仅放行公开示例的五个静态 GET 资源。被动监听保存方法、资源类型、路径摘要、响应状态及 Enter 提交或勾选变更的动作类型。默认关闭浏览器原始 trace 录制。历史公开站原件仅用于核对原运行。

## Risks And Follow-up

公开练习站没有登录。验收以可见浏览器中注入的过期提示复现该前置条件。

## Validation Evidence

skills/ui-test/tests/test_reuse_failure.py 验证精确暂停范围和已选未进入的归因；.scratch/reuse17 保存正常节点的故障夹具及原始运行日志。
