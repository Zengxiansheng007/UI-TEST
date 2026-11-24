# CR-20261124-033-exploration-delivery · 探索批次交付

| Field | Value |
|---|---|
| Status | validated |
| Target Skill | ui-test-explore |
| Change Type | changed |
| Scope | core-skill-md, scripts-and-validation, references-and-assets, downstream-and-handoff |
| Source | UI-TEST #33 under #31 |
| Baseline | ec740c8 |
| Author | Codex |

## Summary

按一次探索批次归集已记录的步骤，再返回独立的离线 HTML。

## Context And Problem

逐动作的适配器与旧交接没有负责整批探索的报告收尾。

## Sections Changed

Workflow、批次调用说明、Node 运行入口和 Python 观察记录适配器。

## Detailed Change

探索保留每例的实际动作、观察、停止位置，以及可选的本地原生回放。专项输入复用同一入口。

## Decision And Alternatives

在既有 Midscene fixture 中包住整批用例。复用 #32 的生成器，避免按单个模型动作交付多个报告。

## Impact Analysis

探索交接新增 report_url 与 observations。正式执行独立读取自己的 V5。历史专项归档保持原路径。

## Validation Evidence

从仓库根目录运行 `node --test tests/exploration_stage.test.cjs` 验证连续用例、受阻、剩余清单和重复运行保护。真实页面验收见 #38。

## Safety And Privacy

测试仅使用受控记录。接入已有页面仍按准确运行包及模型权限执行。调用方负责屏幕数据和自由文本脱敏。

## Risks And Follow-up

已存在的原生回放可附加。进程被强杀时，运行时可能来不及交付已观察的内容。
