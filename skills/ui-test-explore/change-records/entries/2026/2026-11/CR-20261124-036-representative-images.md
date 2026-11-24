# CR-20261124-036 · 代表图与来源

| Field | Value |
|---|---|
| Status | validated |
| Target Skill | ui-test-explore |
| Baseline | 604a6d2 |

## Summary

#36（R06–R07、AC-05/07）。作者指定可证明目标的代表图，并可逐张访问有效证据。

## Context And Problem

原入口逐图常显，无法区分重复画面与状态变化。

## Sections Changed

exploration-delivery.md 及配套运行入口。正式与探索采图记录观察语义，报告生成器判定代表图并生成离线索引。

## Decision And Alternatives

使用现场观察的对象、时点、状态及作者依据，仅在一次尝试内归组。旧图缺少必要字段时独立展示。路径和摘要用于证明来源与字节完整性。

## Impact Analysis

同一组有多个直接证明时采用指定者，否则选取首张直接证明。仅有上下文或缺图时告知审阅限制；已封存结果保持原值。

## Validation Evidence

c31-evidence/36 保存两阶段受控交付物、正式 V5、探索观察与核验结果。本地页面显示合成对象 A-17、A-18，未调用模型。独立浏览器检查逐图归属、查看器、最终目标和状态变化。

## Safety And Privacy

只读解析已记录现场，控制样本的说明与画面使用虚构内容。提交前检查本轮差异，技能包运行敏感字段扫描。

## Risks And Follow-up

观察者负责如实标注画面是否直接证明目标。真实公开页结果由 #38 单独记录。
