# scripts-and-validation

- [CR-20261124-138 · 阶段交付复核修复](../entries/2026/2026-11/CR-20261124-138-stage-publication-review.md)

## Purpose

Changes affecting scripts-and-validation.

## Outline

- [CR-20261127-076 · Formal write budget](../entries/2026/2026-11/CR-20261127-076-formal-budget.md)

- [CR-20261120-031 · 原始事务与未知执行接续](../entries/2026/2026-11/CR-20261120-031-authoritative-session.md)

- [CR-20261120-022](../entries/2026/2026-11/CR-20261120-022-formal-concurrency.md) · 执行进程领取 attempt 并归档输出。定向恢复取得执行锁后复核绑定的目标、终态及提交回执。

- CR-20261120-026 · 入口与共享待办示例、决定复用函数及针对性测试。

See the linked change records.

## Detailed Records

- [CR-20261127-079 · Offline batch report](../entries/2026/2026-11/CR-20261127-079-batch-reader.md)
- [CR-20261127-075](../entries/2026/2026-11/CR-20261127-075-unknown-write.md)
- [CR-20261127-078 · Network verification](../entries/2026/2026-11/CR-20261127-078-network-review.md)

### CR-20261120-031 · 原始事务与未知执行接续

ui-test core verifies the owner-bound transaction and node identity. The dispatcher retains an unknown run, waits for physical process exit and applies its serial scopes and concrete conflicts to later nodes. Both modes recheck a cached pass on re-entry. Concrete serial scopes now appear with the decision reference. [Details](../entries/2026/2026-11/CR-20261120-031-authoritative-session.md)

### CR-20261120-022 · 正式执行

执行进程领取 attempt 并归档输出。定向恢复取得执行锁后复核绑定的目标、终态及提交回执。 变更依据、前后行为及验证见[详细记录](../entries/2026/2026-11/CR-20261120-022-formal-concurrency.md)。

- [CR-20261119-020 · #12 集成修复的逐步暂停及环境证据](../entries/2026/2026-11/CR-20261119-020-integration-failures.md)

- [CR-20261119-019 · 两行定位修复与新版复用](../entries/2026/2026-11/CR-20261119-019-scoped-locator-repair.md)

- [CR-20261119-016 · 探索经验和脚本复用](../entries/2026/2026-11/CR-20261119-016-strategy-learning.md)

- [CR-20261119-018 · 固定版本与并发决定](../entries/2026/2026-11/CR-20261119-018-atomic-revisions.md)

- [CR-20261119-017 · 失败回执与预算](../entries/2026/2026-11/CR-20261119-017-failure-receipts.md)

- [CR-20261119-015 · 用例资产选择](../entries/2026/2026-11/CR-20261119-015-case-asset-selection.md)

- [CR-20261119-014 · Project asset discovery](../entries/2026/2026-11/CR-20261119-014-project-discovery.md)

- [CR-20261119-013 · TodoMVC 源用例导航证据](../entries/2026/2026-11/CR-20261119-013-navigation-evidence.md)


- [CR-20261118-004 · Packet 3.0](../entries/2026/2026-11/CR-20261118-004-packet.md)
- [CR-20261118-007 · 指定用例启动](../entries/2026/2026-11/CR-20261118-007-specified-runner.md)
- [CR-20261118-006 · ModuleReadyContext 2.0](../entries/2026/2026-11/CR-20261118-006-module-ready.md)
- [CR-20261118-008 · 分阶段提交](../entries/2026/2026-11/CR-20261118-008-staged-submit.md)

- [CR-20261118-009 · Passive network evidence](../entries/2026/2026-11/CR-20261118-009-passive-network.md)


---

# Scripts And Validation Change Ledger

## Purpose

Track deterministic runtime, compiler, validator and test changes.

## Outline

| Date | Change ID | Section | Change Type | Summary | Status |
|---|---|---|---|---|---|
| 2026-09-04 | CR-20260904-002 | finalization store/transaction, V5 linker, plugin lifecycle and focused validation | added | Enforce content-addressed atomic finalization, failure receipts, session projection and legacy read-only behavior | applied |
| 2026-09-04 | CR-20260904-001 | execution context, lock, attempt, deployment and V4 validation | added | Add v2.1 contracts, universal plugin, R2 lock, append-only lifecycle, terminal-after RunResultV4 and readiness; ST-010 keeps global tests self-contained while adapter deployment tests remain project-owned; ST-011 keeps qualification terminal evidence while skipping the ordinary RunResult finalizer | applied |
| 2026-09-03 | CR-20260903-001 | compiler, aggregate, case sync and tests | changed | Enforce per-module postconditions, hierarchical aggregate Golden and inactive successor lifecycle | validated |
| 2026-09-02 | CR-20260902-002 | Compiler v2 Playwright renderer and live readiness tests | fixed | Generate formal pytest identity/risk markers and validate live-adapter contracts | proposed |
| 2026-09-02 | CR-20260902-001 | v2 contracts, compiler, sync, guard, diagnostics and tests | added | Implement the approved parameter-governance and migration closure in a workspace candidate | validated |
| 2026-08-18 | CR-20260818-001 | scripts/ui_test_core and tests | added | Add standard-library validator and contract tests | applied |
| 2026-08-22 | CR-20260822-001 | scripts/ui_test_core/registry_validator and tests | added | Add contract registry and source baseline validator with lifecycle state support | applied |
| 2026-08-22 | CR-20260822-002 | schemas, scripts/ui_test_core/case_contracts and tests | added | Add Source Case and IR contracts with RFC 8785 canonical hashing | applied |
| 2026-08-22 | CR-20260822-003 | project config schema/loader, Path Planner and tests | added | Enforce v2 write config, asset-type roots, business hierarchy and Windows containment | applied |
| 2026-08-22 | CR-20260822-004 | Packet v2 schema/validator, migration adapter and tests | changed | Centralize legacy adaptation and machine-readable fail-closed issues | applied |
| 2026-08-22 | CR-20260822-005 | preflight/post-write gate, sensitive scanner and tests | added | Block invalid config, contract, path, secret, migration and release states | applied |
| 2026-08-22 | CR-20260822-007 | private pilot templates and candidate validation | fixed | Add R2 runtime tests, exact-host guard and current validator compatibility | validated |
| 2026-08-22 | CR-20260822-008 | pilot pytest config and sensitive-scan fixture | fixed | Register governed markers and distinguish explicit environment references from secret values | validated |
| 2026-08-22 | CR-20260822-009 | CompletionEvaluator migration status | fixed | Preserve failed versus deferred migration semantics with boolean compatibility | validated |
| 2026-08-25 | CR-20260825-001 | scripts/ui_test_core/semantic_rules and tests | added | Add Semantic Rule Registry, stable Issue List, pre-lowering validation and parameter atomization | validated |
| 2026-08-25 | CR-20260825-002 | product aggregate, JCS wrapper, semantic rules and tests | added | Add product Markdown/outline projection, P0 joint coverage, RFC 8785 dependency gate and A/B semantic repair coverage | validated |
| 2026-08-25 | CR-20260825-003 | runtime dependency metadata | changed | Install pytest 9.1.1, lock the dependency and validate the full pytest suite | validated |

## Detailed Records

### CR-20260904-002 - pycharm-finalization-transaction-v2

- Section changed: finalization store/transaction, RunResultV5 linker, pytest lifecycle, completion projection and tests.
- Before: successful terminal preceded project finalization and two fixed files had no atomic commit point.
- After: objects are content addressed, one manifest commits them, receipt precedes terminal, failures remain observable and session/acceptance are separate.
- Why: close the real PyCharm exit=1 split-brain defect and partial-write risk.
- Impact: new formal execution requires the V5 path; V3/V4 validators remain unchanged and read-only.
- Validation: transaction plus V3/V4/V5 linker and contract focused suite passed; full plugin/adapter/helper matrix remains pending.
- Detail record: `../entries/2026/2026-09/CR-20260904-002-pycharm-finalization-transaction-v2.md`.

### CR-20260902-001 - test-data-sync-execution-governance

- Section changed: schemas, `scripts/ui_test_core`, validators, migration tooling and tests.
- Before: business parameters had no dedicated v2 contract, compiler manifest coverage was incomplete, and execution/logging lacked a unified hash gate.
- After: proposed v2 contracts and deterministic implementations cover parameter ownership, synchronization, execution snapshots and failure/repair projections.
- Why: eliminate A/B parameter dual sources and restore execution eligibility through controlled migration.
- Impact: v1 remains audit-only; new execution eligibility requires the complete v2 gates.
- Validation: 247 tests passed; structure validator reported P0/P1/P2 zero; candidate sensitive scan reported zero findings; A/B migration and zero-delete cleanup rehearsal passed.
- Detail record: `../entries/2026/2026-09/CR-20260902-001-test-data-sync-execution-governance.md`.

### CR-20260822-007 - candidate-validation-and-pilot-runtime

- Section changed: private pilot generator, runner and validation fixtures.
- Before: no generated Approval Record or canonical failure result.
- After: generated runtime persists redacted approval and RunResult evidence.
- Why: PH-05 exit requirements and final package validation.
- Impact: private network failures remain zero-submit and machine-readable.
- Validation: 99 tests plus warning-free two-case pytest collection.
- Detail record: `../entries/2026/2026-08/CR-20260822-007-candidate-validation-and-pilot-runtime.md`.

### CR-20260822-008 - pytest-marker-and-env-reference-governance

- Section changed: pilot pytest configuration, private runner metadata and sensitive scan tests.
- Before: manual collection emitted unknown-marker warnings and a password environment-variable name resembled a literal credential assignment.
- After: five governed markers are registered and runtime value mappings use an explicit `env_ref` object.
- Why: keep manual pytest execution warning-free without weakening secret detection.
- Impact: generated and current pilot assets share one marker contract; real credential literals remain blocked.
- Validation: 101 tests, warning-free two-case collection and dual-scope sensitive scan.
- Detail record: `../entries/2026/2026-08/CR-20260822-008-pytest-marker-and-env-reference-governance.md`.

### CR-20260822-009 - deferred-migration-completion-status

- Section changed: CompletionEvaluator and final governance evidence builder.
- Before: every non-passed migration state emitted `migration-failed`.
- After: governed `passed`, `failed` and `deferred` states emit precise blockers while legacy booleans remain supported.
- Why: the first-pilot migration dry-run passed, but historical disposition is deferred until private validation completes.
- Impact: completion remains blocked with accurate machine-readable semantics.
- Validation: completion compatibility and deferred-state regression tests.
- Detail record: `../entries/2026/2026-08/CR-20260822-009-deferred-migration-completion-status.md`.

### CR-20261120-026 · 编写前核对共享状态

正式脚本派发前核对用户消息、批次节点和具体冲突。 验证及范围见[详细变更记录](../entries/2026/2026-11/CR-20261120-026-shared-state.md)。

### CR-20261120-028 · 人工并行与显式串行

- 变更了正常 pytest 入口的显式范围、重投保护与结果投影。
- [变更详情](../entries/2026/2026-11/CR-20261120-028-manual-concurrency.md)

### CR-20261120-029 · Codex 明确指令并行

- [变更详情](../entries/2026/2026-11/CR-20261120-029-codex-parallel.md)记录指令范围、冲突复用、派发与逐例验收。

### CR-20261124-032 · 正式执行的阶段报告

pytest controller 和 Codex 整批收尾核对已提交的会话与各用例 V5，再交付一个离线链接。 [详情](../entries/2026/2026-11/CR-20261124-032-formal-stage-delivery.md)

- [CR-20261124-034 · 阶段报告离线审阅](../entries/2026/2026-11/CR-20261124-034-stage-reading.md)

- [CR-20261124-035 · 运行中采集步骤截图](../entries/2026/2026-11/CR-20261124-035-stage-capture.md)

- [CR-20261124-037 · 阶段异常与尝试归属](../entries/2026/2026-11/CR-20261124-037-stage-outcomes.md)

- [CR-20261124-135 · R0 正式断言、V5 与零提交收据](../entries/2026/2026-11/CR-20261124-135-read-only-finalization.md)

- [CR-20261124-036 · 代表图与来源](../entries/2026/2026-11/CR-20261124-036-representative-images.md)

- [CR-20261125-043 · 旧项目脚本与报告原位登记](../entries/2026/2026-11/CR-20261125-043-legacy-discovery.md)

- [CR-20261125-042 · 项目运行目录与按尝试查询](../entries/2026/2026-11/CR-20261125-042-stage-catalog.md)

- [CR-20261125-044 · 执行时版本绑定](../entries/2026/2026-11/CR-20261125-044-execution-version.md)

- [CR-20261125-045 · 阶段中断补登](../entries/2026/2026-11/CR-20261125-045-replay.md)

- [CR-20261125-048 · 项目产物盘点与使用方](../entries/2026/2026-11/CR-20261125-048-project-inventory.md)

- [CR-20261125-046 · 阶段原件与关联报告](../entries/2026/2026-11/CR-20261125-046-stage-links.md)

- [CR-20261125-049 · 阶段保留与预演](../entries/2026/2026-11/CR-20261125-049-stage-retention.md)

- [CR-20261125-047 · 按中文用例名查当前脚本](../entries/2026/2026-11/CR-20261125-047-current-scripts.md)

- [CR-20261125-050 · Windows 定时生成待审清单](../entries/2026/2026-11/CR-20261125-050-windows-preview.md)

- [CR-20261125-051 · 批准与阶段归档核验](../entries/2026/2026-11/CR-20261125-051-stage-archive.md)

- [CR-20261125-052 · 批准范围内释放工作副本](../entries/2026/2026-11/CR-20261125-052-stage-release.md)

- [CR-20261125-053 · 离线历史目录与阶段恢复](../entries/2026/2026-11/CR-20261125-053-archive-history.md)


- [CR-20261125-054 · 从已批准批次继续归档与释放](../entries/2026/2026-11/CR-20261125-054-resume-archive.md)

- [CR-20261127-058 · Selected stage report owner](../entries/2026/2026-11/CR-20261127-058-report-suite.md) — Select a single suite catalog, core and report owner for both producers.
- [CR-20261127-061 · 历史运行查询](../entries/2026/2026-11/CR-20261127-061-run-catalog.md)

- [CR-20261127-062 · Asset and experience owners](../entries/2026/2026-11/CR-20261127-062-asset-experience-owners.md)

- [CR-20261127-063](../entries/2026/2026-11/CR-20261127-063-verify-script-build.md) Verification and script building.

- [CR-20261127-064 · Selected-suite handoff](../entries/2026/2026-11/CR-20261127-064-selected-handoff.md)

- [CR-20261127-070 · Formal execution owner](../entries/2026/2026-11/CR-20261127-070-playwright-run.md)

- [CR-20261127-071 · Selected suite routing](../entries/2026/2026-11/CR-20261127-071-selected-suite-routing.md)

[CR-20261127-065](../entries/2026/2026-11/CR-20261127-065-checkpoint.md) — Selected checkpoint owner, standalone definition check and historical adapter.

- [CR-20261127-066](../entries/2026/2026-11/CR-20261127-066-current-session.md)

[CR-20261127-067](../entries/2026/2026-11/CR-20261127-067-repair.md) — Offline repair and historical compatibility.

- [CR-20261127-068](../entries/2026/2026-11/CR-20261127-068-artifact-governance.md)

- [CR-20261127-072 · Approved multi-stage workflow](../entries/2026/2026-11/CR-20261127-072-selected-workflow.md)

- [CR-20261127-074 · Independent report reader](../entries/2026/2026-11/CR-20261127-074-offline-report.md)

### CR-20261127-076 · Scoped formal write permits

The approved node and phase limit restricts protected writes before the click. See the [change and controlled regression evidence](../entries/2026/2026-11/CR-20261127-076-formal-budget.md).

CR-20261127-076 also covers a denied reservation followed by an interrupted worker in the same serial report.
