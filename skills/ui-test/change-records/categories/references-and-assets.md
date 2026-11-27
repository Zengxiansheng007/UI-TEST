# references-and-assets

## Purpose

Changes affecting references-and-assets.

## Outline

- [CR-20261120-031 · 主包文件基线](../entries/2026/2026-11/CR-20261120-031-authoritative-session.md)

- [CR-20261120-022](../entries/2026/2026-11/CR-20261120-022-formal-concurrency.md) · 新增 2.4 配置模板及 V5 上下文、V2 会话契约，兼容 2.3 和历史结果。

- CR-20261120-026 · 入口与共享待办示例、决定复用函数及针对性测试。

See the linked change records.

## Detailed Records

### CR-20261120-031 · 主包文件基线

新增本轮变更记录后，按仓库跟踪文件重新核对主包 284 个文件与现行 SKILL.md 摘要。[验证与变更记录](../entries/2026/2026-11/CR-20261120-031-authoritative-session.md)

### CR-20261120-022 · 正式执行

新增 2.4 配置模板及 V5 上下文、V2 会话契约，兼容 2.3 和历史结果。 变更依据、前后行为及验证见[详细记录](../entries/2026/2026-11/CR-20261120-022-formal-concurrency.md)。

- [CR-20261119-016 · 探索经验和脚本复用](../entries/2026/2026-11/CR-20261119-016-strategy-learning.md)

- [CR-20261119-015 · 用例资产选择](../entries/2026/2026-11/CR-20261119-015-case-asset-selection.md)

- [CR-20261119-013 · TodoMVC 源用例导航证据](../entries/2026/2026-11/CR-20261119-013-navigation-evidence.md)


- [CR-20261118-004 · Packet 3.0](../entries/2026/2026-11/CR-20261118-004-packet.md)
- [CR-20261118-007 · 指定用例启动](../entries/2026/2026-11/CR-20261118-007-specified-runner.md)

- [CR-20261118-006 Readiness schema](../entries/2026/2026-11/CR-20261118-006-module-ready.md)
- [CR-20261118-008 · 分阶段提交](../entries/2026/2026-11/CR-20261118-008-staged-submit.md)

- [CR-20261118-009 · Active package baseline](../entries/2026/2026-11/CR-20261118-009-passive-network.md)


---

# References And Assets Change Ledger

## Purpose

Track schemas, fixtures, references and generated-asset contracts.

## Outline

| Date | Change ID | Section | Change Type | Summary | Status |
|---|---|---|---|---|---|
| 2026-09-04 | CR-20260904-002 | 2.2/V3/AttemptV2/V5/finalization/session/acceptance references and contracts | added | Define transactional result closure, failure evidence and historical read-only boundary | applied |
| 2026-09-04 | CR-20260904-001 | v2.1/V4/readiness schemas, fixtures and deployment-source assets | added | Add stable execution context, attempt, approval, V4 and readiness contracts plus the current-Demo-derived v2.1 adapter configuration source | applied |
| 2026-09-03 | CR-20260903-001 | v2 schemas and asset governance | changed | Add page-module, product-outline, aggregate-manifest and pre-submit qualification contracts | validated |
| 2026-09-02 | CR-20260902-001 | schemas, fixtures and asset-governance reference | added | Define the v2 parameter, release, diagnostics, migration and cleanup artifact family | validated |
| 2026-08-18 | CR-20260818-001 | schemas/assets/fixtures | added | Add versioned packet schema and valid/invalid fixtures | applied |
| 2026-08-22 | CR-20260822-001 | schemas/contract-registry.json | changed | Extend registry with planned Source Case, Case IR, Resolved IR and Compile Receipt entries | applied |

## Detailed Records

### CR-20260904-002 - pycharm-finalization-transaction-v2

- Section changed: asset governance, execution contracts, workflow contract and new versioned finalization family.
- Before: no atomic multi-artifact commit, session result or external process-exit acceptance contract.
- After: content-addressed objects, one commit manifest, receipt, SessionResult and AcceptanceResult form separate hash-bound layers.
- Why: a fixed RunResult/evidence write pair can leave an accepted half-result and cannot prove original process exit.
- Impact: readers must follow the new closure; historical artifacts remain byte-readable and ineligible for upgrade.
- Validation: Schema/transaction/linker focused tests passed; full candidate validation remains pending.
- Detail record: `../entries/2026/2026-09/CR-20260904-002-pycharm-finalization-transaction-v2.md`.

### CR-20260902-001 - test-data-sync-execution-governance

- Section changed: contract registry, v2 schemas, fixtures and project-asset governance.
- Before: Source Case v1 carried business values and no complete v2 artifact family was registered.
- After: proposed contracts separate Source Case semantics from branch-level editable Test Data and generated projections.
- Why: ensure one editable business-data source and deterministic downstream assets.
- Impact: old-format artifacts remain readable for audit but cannot execute.
- Validation: every registered Schema passed Draft 2020-12 meta-validation and positive/negative registry tests.
- Detail record: `../entries/2026/2026-09/CR-20260902-001-test-data-sync-execution-governance.md`.

### CR-20260822-007 - candidate-validation-and-pilot-runtime

- Section changed: no reference contract behavior changed.
- Before: package references predated the current validator.
- After: reference links are validated as bounded resources.
- Why: final package traceability.
- Impact: documentation only in this category.
- Validation: reference existence checks.
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

### CR-20261124-032 · 正式执行的阶段报告

pytest controller 和 Codex 整批收尾核对已提交的会话与各用例 V5，再交付一个离线链接。 [详情](../entries/2026/2026-11/CR-20261124-032-formal-stage-delivery.md)

- [CR-20261124-035 · 运行中采集步骤截图](../entries/2026/2026-11/CR-20261124-035-stage-capture.md)

- [CR-20261124-135 · R0 正式断言、V5 与零提交收据](../entries/2026/2026-11/CR-20261124-135-read-only-finalization.md)

- [CR-20261124-036 · 代表图与来源](../entries/2026/2026-11/CR-20261124-036-representative-images.md)

- [CR-20261125-043 · 旧项目脚本与报告原位登记](../entries/2026/2026-11/CR-20261125-043-legacy-discovery.md)

- [CR-20261127-058 · Selected stage report owner](../entries/2026/2026-11/CR-20261127-058-report-suite.md) — Select a single suite catalog, core and report owner for both producers.

- [CR-20261127-060 · Step evidence and review routing](../entries/2026/2026-11/CR-20261127-060-step-evidence-routing.md)

- [CR-20261127-061 · 历史运行查询](../entries/2026/2026-11/CR-20261127-061-run-catalog.md)

- [CR-20261127-062 · Asset and experience owners](../entries/2026/2026-11/CR-20261127-062-asset-experience-owners.md)

- [CR-20261127-063](../entries/2026/2026-11/CR-20261127-063-verify-script-build.md) Verification and script building.

- [CR-20261127-064 · Selected-suite handoff](../entries/2026/2026-11/CR-20261127-064-selected-handoff.md)

- [CR-20261127-069 · Standalone exploration](../entries/2026/2026-11/CR-20261127-069-standalone-exploration.md) — The selected suite resolves explore and ui-test-explore to a single owner.

- [CR-20261127-070 · Formal execution owner](../entries/2026/2026-11/CR-20261127-070-playwright-run.md)

- [CR-20261127-071 · Selected suite routing](../entries/2026/2026-11/CR-20261127-071-selected-suite-routing.md)

[CR-20261127-065](../entries/2026/2026-11/CR-20261127-065-checkpoint.md) — Checkpoint validation and suite routing.

- [CR-20261127-066](../entries/2026/2026-11/CR-20261127-066-current-session.md)

[CR-20261127-067](../entries/2026/2026-11/CR-20261127-067-repair.md) — Offline repair and historical compatibility.

- [CR-20261127-068](../entries/2026/2026-11/CR-20261127-068-artifact-governance.md)
