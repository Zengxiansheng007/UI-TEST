# CR-20261120-029 · Codex 明确指令并行

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Change Type | changed |
| Scope | core-skill-md, references-and-assets, scripts-and-validation, safety-and-governance |
| Source | UI-TEST #22, #29 |
| Baseline | 9e88413 |
| Author | Codex |
| Related Records | CR-20261120-026, CR-20261120-028 |

## Summary

从正式调度入口执行用户明确指名并发的节点，保留可追溯的消息引用和逐例结果。

## Context And Problem

原入口对所有批次逐例等待子进程退出，无法表达当前任务明确授予的并发范围。

## Sections Changed

主技能、共享状态参考、派发启动器、pytest 调度插件、任务日志和正常入口回归用例。

## Decision And Alternatives

复用现有任务文件锁、正式收集、每例执行插件和会话证据核验。可用时选择 xdist 的 load 调度；独立进程使用各自的会话。

## Detailed Change

调度器核对任务、批次、指令引用和收集得到的具体节点。它在同一范围内复用已接受的明确冲突，安排显式串行范围分次运行。观察子进程保存真实退出，重入后分别核查各节点的终态和回执。

## Impact Analysis

无并行指令的旧入口和人工入口继续使用原契约。worker 与独立进程记录同一任务意图，每个正式节点仍单独核对 R2 写入批准与预算。

## Validation Evidence

专项验收目录 `t29` 保留正常入口失败基线和候选测试结果。合成用例覆盖节点隔离、双 worker、独立进程、缺失依赖、具体风险决定、串行政策和结果未知时重入。

## Safety And Privacy

指令文件仅包含脱敏的消息、对象及证据引用，业务操作继续经原 pytest 运行插件和逐例事务执行。

## Risks And Follow-up

浏览器内的真实业务时间、逐例断言和原回执由独立验收记录。
