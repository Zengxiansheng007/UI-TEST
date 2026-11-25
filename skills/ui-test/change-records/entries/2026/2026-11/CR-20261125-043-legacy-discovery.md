# CR-20261125-043 · 旧项目脚本与报告原位登记

| Field | Value |
|---|---|
| Status | validated |
| Target Skill | ui-test |
| Baseline | 7180a5d |
| Requirement | #43, P1-R03, P1-AC-03 |

## Summary

项目目录可登记有来源的旧脚本与报告。生效脚本经过发布校验，原报告可在原位置打开。

## Context And Problem

既有目录保存多个同名脚本。生效版本需要从原用例分支的 active.json、发布清单、编译收据和发布文件交叉核实。

## Sections Changed

新增 legacy_inventory.py 和相应测试。在 reporting-and-promotion.md 说明项目级扫描配置和诊断。#42 的项目刷新入口消费发现结果。

## Decision And Alternatives

扫描工程师列出的项目内目录，调用既有发布完整性检查。来源与目标均记录项目相对位置。遇到缺件、归属冲突或未核实版本时保留具体原因。

## Impact Analysis

在旧报告所在地解析链接。多份指针声称相同用例分支时标为待核。发现只读原件，支持隔离复制项目后的再次刷新。

## Validation Evidence

基线红测记录缺少发现入口；六项定向检查覆盖发现和既有发布核验。公开 TodoMVC 历史用例的三版脚本及旧正式报告的隔离副本存于 p39-evidence/43/sample，逐项发现结果在 discovery.json。

## Safety And Privacy

仅访问配置目录，跳过私有材料、版本控制目录及重解析点。发现过程不执行旧脚本或访问外部链接。

## Risks And Follow-up

仅可交叉核实的 v2 发布有生效结论。普通脚本保留待核，时间未知。正常刷新入口与离线目录由 #42 共同验证。
