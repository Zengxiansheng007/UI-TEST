# CR-20261124-139 · 单次报告归档隔离

| Field | Value |
|---|---|
| Target Skill | ui-test-execution-report |
| Baseline | 9845561 |
| Status | applied |

## Summary

单次 V5 的阶段报告和历史诊断分目录发布四项文件，CLI 返回报告 URL 和各文件路径。

## Context And Problem

在同一输出根目录交替使用两种模式时，后一次会覆盖先前的 HTML 和机器资料。

## Sections Changed

单次报告 CLI、输出目录契约、生成物校验器及 CLI 回归。

## Decision And Alternatives

显式诊断沿用既有布局，阶段导出使用独立的 stage-reports 目录。重交付复用各模式的运行路径。

## Impact Analysis

隔离适用于 --input 的两种渲染模式，生成物校验器分别核对各自的 HTML 和机器资料。

## Validation Evidence

两种生成顺序交替重试，逐次对比 HTML、执行摘要、证据索引和 V5 的 SHA-256。修复前后记录位于 c31-evidence/review/isolation-red.xml 和 isolation-green.xml。

## Safety And Privacy

只使用包内脱敏 V5 样本及本机临时目录。

## Risks And Follow-up

已被早期候选版本实际覆盖的归档若需恢复，须另有原始副本。
