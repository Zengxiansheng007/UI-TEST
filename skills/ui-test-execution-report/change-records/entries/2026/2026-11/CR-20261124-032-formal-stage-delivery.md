# CR-20261124-032 · 正式执行的阶段报告

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test-execution-report |
| Change Type | added |
| Scope | scripts-and-validation, references-and-assets |
| Source | UI-TEST #31, #32 |
| Baseline | 435879e129d55adac2dbd45d51fe69ae5b86ce86, skill tree 2f1792b1cb777e67cc83cedb123459e99f69cfae |
| Author | Codex |
| Related Records | CR-20261120-025 |

## Summary

共用阶段生成操作接收运行身份与有序用例，生成一份 HTML、证据索引和执行摘要。

## Context And Problem

会话结束只归档了机器可读结果。Codex 串行调度每个节点有自己的子会话。

## Sections Changed

阶段报告生成、会话收尾、Codex 调度与回归验证，以及包内使用说明。

## Decision And Alternatives

worker 只提交用例证据。发布入口读取封存的会话与事务，先生成完整内容，再替换最终 HTML。

## Detailed Change

每次阶段包含所有用例的目录、步骤和来源。重复完成同一运行获得同一链接，来源冲突给出校验错误。
保留原始 V5、单用例 CLI 和历史报告。

## Impact Analysis

执行环境需要并列部署 ui-test 和 ui-test-execution-report。缺少报告包时收尾提示 E_STAGE_REPORT_PACKAGE_REQUIRED。

## Validation Evidence

受控 pytest 单用例和双用例核对 V5、步骤和尝试。串行 Codex 两次交付核对链接相同、执行次数相同。
外部运行证据位于 c31-evidence/32。

## Safety And Privacy

受控用例仅操作本地夹具。报告过程没有浏览器或业务请求。
发布前复用报告包的敏感字段扫描，HTML 对业务文字转义。

## Risks And Follow-up

本票核验正式阶段。探索入口、截图交互、异常细节与公开页面验收分别由后续工单覆盖。
