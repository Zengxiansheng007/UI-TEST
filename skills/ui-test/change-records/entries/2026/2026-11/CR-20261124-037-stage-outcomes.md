# CR-20261124-037 · 阶段异常与尝试归属

| Field | Value |
|---|---|
| Status | validated |
| Target Skill | ui-test |
| Baseline | a008d7d |

## Summary

批次收尾按会话引用、摘要、节点和运行匹配原始 V5。保留独立尝试，拒绝同一会话行重复投递。

## Context And Problem

UI-TEST #37 的正式和探索报告需区分缺失画面、结果未知及未执行。原有批次合并会把同一节点不同会话的两次运行判为重复节点。

## Sections Changed

本技能的阶段报告适配或投影、行为验证和变更记录。各技能的确切边界见概要。

## Decision And Alternatives

正式端逐项绑定会话、节点和运行并复用已封存 V5。探索端保留当前查证的动作，并以显式停止位置解释剩余步骤。只为同一份观察归档重新运行 Python 发布入口。

## Impact Analysis

阶段报告保留不同尝试。来源身份冲突会阻止交付。既有 V5 结论、单用例 CLI 和正式运行的串行策略继续适用。

## Validation Evidence

受控样本在 c31-evidence/37。formal.log 保存同一 CASE-STAGES 两次封存 V5 的运行输出，预期一次失败、一次成功。verified.json 记录通过正式与探索归档入口重交付，核对原始文件摘要和各尝试的图，审计禁止网络及进程启动。green.log 和 batch-red.log 保留探索回归与修复前的批次失败。公开页面验收归 #38，受控材料只验证异常分支。

## Safety And Privacy

样本数据源为本地受控夹具，图片只存在第二次尝试。重交付时禁止网络及启动子进程，24 份源记录摘要不变。

## Risks And Follow-up

历史观察缺少步骤清单且没有停止边界时，仅能报告已记录的信息。受控样本覆盖故障行为，公开测试页的工程师审阅属于 #38。
