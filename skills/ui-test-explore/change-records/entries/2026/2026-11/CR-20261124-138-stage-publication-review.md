# CR-20261124-138 · 阶段交付复核修复

| Field | Value |
|---|---|
| Target Skill | ui-test-explore |
| Baseline | 0190b97 |
| Status | applied |

## Summary

正常截图生成独立归属凭据。归档核对运行、用例、尝试、步骤、原图来源及摘要。采集或存储失败留在实际步骤。

## Context And Problem

父规格 #31 AC-02、AC-07、AC-08 复核发现证据归属、失败现场和旧入口兼容缺口。

## Sections Changed

技能脚本、相关说明和针对性回归见本提交。

## Decision And Alternatives

归档使用采集时已记录的证据，只有可核验来源的图片才能展示。保留原有机器摘要和诊断。

## Impact Analysis

原有历史 HTML 按原样保存；新阶段报告按真实记录展示。正常交付读取归档，无业务写入。

## Validation Evidence

本地回归与包验证见 c31-evidence/review。受控样本覆盖拒绝敏感文本、归属和摘要冲突、缺图及异常现场。公开页面独立验收归 #38。

## Safety And Privacy

用合成字符串和本地夹具复核，凭据信息仅返回固定错误代码。

## Risks And Follow-up

旧归档若无可信字节摘要，只能呈现引用及缺口。
