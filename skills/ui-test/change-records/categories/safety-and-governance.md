# safety-and-governance

- [CR-20261124-138 · 阶段交付复核修复](../entries/2026/2026-11/CR-20261124-138-stage-publication-review.md)

## Purpose

记录本类别的变更及复核依据。

## Outline

- [CR-20261127-076 · Formal write budget](../entries/2026/2026-11/CR-20261127-076-formal-budget.md)

- [CR-20261120-031 · 原始事务与未知执行接续](../entries/2026/2026-11/CR-20261120-031-authoritative-session.md)

- [CR-20261120-022](../entries/2026/2026-11/CR-20261120-022-formal-concurrency.md) · 活动运行、未绑定的历史运行及错误恢复目录均保持只读，原业务写入次数仍按例核对。

- CR-20261120-026 · 入口与共享待办示例、决定复用函数及针对性测试。

## Detailed Records

- [CR-20261127-075](../entries/2026/2026-11/CR-20261127-075-unknown-write.md)

### CR-20261120-031 · 原始事务与未知执行接续

ui-test core verifies the owner-bound transaction and node identity. The dispatcher retains an unknown run, waits for physical process exit and applies its serial scopes and concrete conflicts to later nodes. Both modes recheck a cached pass on re-entry. Concrete serial scopes now appear with the decision reference. [Details](../entries/2026/2026-11/CR-20261120-031-authoritative-session.md)

### CR-20261120-022 · 正式执行

活动运行、未绑定的历史运行及错误恢复目录均保持只读，原业务写入次数仍按例核对。 变更依据、前后行为及验证见[详细记录](../entries/2026/2026-11/CR-20261120-022-formal-concurrency.md)。

### CR-20261120-026 · 编写前核对共享状态

正式脚本派发前核对用户消息、批次节点和具体冲突。 验证及范围见[详细变更记录](../entries/2026/2026-11/CR-20261120-026-shared-state.md)。

### CR-20261120-028 · 人工并行与显式串行

- 变更了正常 pytest 入口的显式范围、重投保护与结果投影。
- [变更详情](../entries/2026/2026-11/CR-20261120-028-manual-concurrency.md)

### CR-20261120-029 · Codex 明确指令并行

- [变更详情](../entries/2026/2026-11/CR-20261120-029-codex-parallel.md)记录指令范围、冲突复用、派发与逐例验收。

- [CR-20261124-135 · R0 正式断言、V5 与零提交收据](../entries/2026/2026-11/CR-20261124-135-read-only-finalization.md)

### CR-20261127-076 · Scoped formal write permits

The approved node and phase limit restricts protected writes before the click. See the [change and controlled regression evidence](../entries/2026/2026-11/CR-20261127-076-formal-budget.md).
