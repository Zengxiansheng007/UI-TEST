# core-skill-md

## Purpose

Changes affecting core-skill-md.

## Outline

- CR-20261120-026 · 入口与共享待办示例、决定复用函数及针对性测试。

See the linked change records.

## Detailed Records

- [CR-20261119-015 · 用例资产选择](../entries/2026/2026-11/CR-20261119-015-case-asset-selection.md)


- [CR-20261118-004 · Packet 3.0](../entries/2026/2026-11/CR-20261118-004-packet.md)
- [CR-20261118-007 · 指定用例启动](../entries/2026/2026-11/CR-20261118-007-specified-runner.md)
- [CR-20261118-006 · ModuleReadyContext 2.0](../entries/2026/2026-11/CR-20261118-006-module-ready.md)

- [CR-20261118-009 · Passive network evidence](../entries/2026/2026-11/CR-20261118-009-passive-network.md)


---

# Core Skill MD Change Ledger

## Purpose

Track normative routing, workflow, validation and escalation changes in `SKILL.md`.

## Outline

| Date | Change ID | Section | Change Type | Summary | Status |
|---|---|---|---|---|---|
| 2026-09-04 | CR-20260904-002 | Project Asset Governance, Validation and Escalation | changed | Require 2.2/V3/AttemptV2/V5 transactional close-out and external process acceptance | applied |
| 2026-09-04 | CR-20260904-001 | Execution Context Governance | changed | Require root pytest plugin, v2.1 execution, origin/approval separation and manual A/B completion gate | applied |
| 2026-09-03 | CR-20260903-001 | Project Asset Governance | changed | Require registry-backed module postconditions, recursive product hierarchy and two-phase activation | validated |
| 2026-09-02 | CR-20260902-001 | Project Asset Governance and validation | changed | Route editable branch data through test-data v2 and require v2 compile/sync/execution gates | validated |
| 2026-08-18 | CR-20260818-001 | Unified Packet Contract | changed | Document validator entrypoint and fail-closed boundary | applied |
| 2026-08-22 | CR-20260822-007 | Escalation | added | Add explicit private-page, R2, installation and production gates | validated |

## Detailed Records

### CR-20260904-002 - pycharm-finalization-transaction-v2

- Section changed: formal execution, completion validation and migration boundary.
- Before: V2/V1/V4 allowed terminal-before-finalizer behavior and RunResult self-attested PyCharm/human status.
- After: 2.2/V3/AttemptV2/V5 requires commit plus receipt before terminal, SessionResult and external AcceptanceResult.
- Why: prevent terminal, result and real helper exit from splitting.
- Impact: old 2.1/V2/V1/V4 is audit-only; no installation or R2 authority is granted.
- Validation: focused runtime/contracts passed; full candidate and helper canary remain pending.
- Detail record: `../entries/2026/2026-09/CR-20260904-002-pycharm-finalization-transaction-v2.md`.

### CR-20260822-007 - candidate-validation-and-pilot-runtime

- Section changed: Validation and Escalation.
- Before: no validator-recognized escalation section.
- After: explicit approval and refusal conditions.
- Why: candidate quality gate required a visible safety boundary.
- Impact: no new execution authority.
- Validation: create-skill validator and package tests.
- Detail record: `../entries/2026/2026-08/CR-20260822-007-candidate-validation-and-pilot-runtime.md`.

### CR-20260912-001 - visible-browser-and-run-scope

- Section changed: 可见浏览器与运行额度。
- Before: 未明确显示窗口，批次额度与人工回归容易混淆。
- After: 显式可见窗口、fixture 覆盖检查、按授权范围隔离额度。
- Why: 用户授权修复。
- Impact: 不增加业务写入或模型发送权限。
- Validation: 副本及部署后结构检查零问题、敏感扫描 clear、49 项回归及六例可见窗口零提交资格通过。
- Status: validated
- Detail record: [CR-20260912-001](../entries/2026/2026-09/CR-20260912-001-visible-browser-and-run-scope.md).

### CR-20261120-026 · 编写前核对共享状态

正式脚本派发前核对用户消息、批次节点和具体冲突。 验证及范围见[详细变更记录](../entries/2026/2026-11/CR-20261120-026-shared-state.md)。

### CR-20261120-028 · 人工并行与显式串行

- 变更了正常 pytest 入口的显式范围、重投保护与结果投影。
- [变更详情](../entries/2026/2026-11/CR-20261120-028-manual-concurrency.md)

### CR-20261120-029 · Codex 明确指令并行

- [变更详情](../entries/2026/2026-11/CR-20261120-029-codex-parallel.md)记录指令范围、冲突复用、派发与逐例验收。

- [CR-20261124-135 · R0 正式断言、V5 与零提交收据](../entries/2026/2026-11/CR-20261124-135-read-only-finalization.md)
