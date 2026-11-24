# UI-Test Project Asset Governance

## Scope

These rules apply only to UI-Test project assets. Ordinary workspace files, other Skill assets and global Skill program files are not governed by the D-drive double-root policy.

## Two Non-Overlapping Fact Domains

- Every automated functional branch has exactly one versioned Source Case v2 for test semantics and exactly one sibling `tests/test-data.json` v2 for manually editable business values and generation rules.
- Source Case stores steps, assertions, parameter IDs and typed references; it must not store the referenced business values. Test Data stores values and rules; it must not store locators, actions or assertions.
- Each Source Case v2 step carries one `module_id` and one or more explicit postconditions. A governed `PageModuleRegistry` declares each branch module as `operate`, `assert-default` or `not-applicable`; applicable P0 modules missing an immediate assertion block all projections.
- Human View, Midscene View, Resolved Case, parameter manifest and Python Playwright Test are deterministic projections. They carry `source_case_id`, `branch_id`, `source_hash`, `test_data_hash`, `parameter_manifest_hash`, `dependency_digest`, `build_fingerprint`, generator versions and `do_not_edit=true`.
- Human View uses the step columns `序号`、`操作`、`参数/数据`、`预期结果`; shared account and public data values must show an index or reference path instead of raw secrets.
- The product aggregate is rendered recursively from Case IR v2, Resolved IR v2 and strict manifests. Its fixed tree preserves project-group, product and system levels, emits common prerequisites once, and never concatenates case Human View Markdown.
- Never manually maintain the same case body or business value in multiple formats. Change Source Case for semantics, Test Data for business values/rules, or a shared Flow/Page/Component/binding for automation mechanics; then run plan/sync and validate the active release.
- Release synchronization governs publishing. A specified POC runner executes under its current task authorization.

## Storage

- Execution assets: `D:\UI-Test` only.
- Knowledge, experience and redacted evidence indexes: `D:\RAG` only.
- Staging and model exploration output: `D:\UI-Test\_tmp` or a governed run staging path.
- The project must supply `ui-test.project.yaml` v2 with both roots, stable IDs, display names, system/module/function registry, wait strategy and policy references.
- The project config must declare scoped private `runtime_value_index_ref` and `credential_index_ref` references plus named `runtime_refs`; callers resolve URL and switches through `RuntimeValueLoader` and credentials through the separate credential loader, while legacy `env_ref` names are metadata only.
- `runtime-value-index.yaml` stores environment Runtime values, switches, exploration values and cross-run sequence state; `credential-index.yaml` stores platform-level account credentials; branch `test-data.json` stores case business values and rules. These sources have independent schemas and hashes.
- The Path Planner chooses the root from registered asset type. Callers must not supply `root`, `target_root`, `output_dir` or an arbitrary formal target.
- Use `stable-id__display-name` for business path segments and the fixed hierarchy `project_group/product/system/module_path/function/case/branch/run`.
- Reject C-drive formal UI-Test project assets, root/type mismatch, lexical escape, symlink, junction or reparse-point traversal. Do not report an ordinary C-drive workspace document as a UI-Test violation.

## Case Structure

- Priority is P0, P1 or P2. A P0 page smoke suite may contain multiple user-confirmed branch cases whose declared responsibilities jointly cover all registered primary test points and applicable component variants.
- Separate `setup`, `feature` and `assertions`. A setup failure is `setup/navigation failure`, not a target feature defect.
- Shared login/navigation belongs in versioned Flow objects. Locators and page operations belong in Page/Component objects. Thin tests contain identity, markers and one scenario call; they do not copy locators.
- System announcement plain content and popup announcement rich content are separate Component variants and cannot silently share a binding.

## Compilation And Execution

- The Case Compiler is fixed Python code. Formal plan/sync never calls a model or network to change generated content.
- New writes use the v2 contract family. V1 Source Case, IR, manifests, receipts, releases, runs and reports remain audit-readable but cannot regain execution eligibility without a controlled successor migration.
- Use Draft 2020-12 validation, RFC 8785 canonical hashing, explicit dependency/reverse indexes, immutable releases, expected-active checks and readback validation.
- A v2 manifest enumerates every non-self release attachment. Release integrity, current input sync and execution readiness are independent axes; current drift is never written back into an immutable release.
- Formal semantic successors are published inactive first. A matching `PreSubmitQualificationResult` must prove all non-submit steps and module assertions passed, screenshot evidence is hash-bound, `submit_count=0`, `write_state=not_attempted` and `sequence_allocated=false` before atomic activation.
- Formal regression uses only Python + pytest + pytest-playwright. Each test file and node ID must run independently and as part of the suite; filenames must be unique.
- Every formal test gets a fresh BrowserContext and executes the complete login/menu/function Flow. Midscene exploration may use a current-session ready checkpoint route, but a formal Playwright test never skips the full precondition Flow.

## R2 And Results

- R2 approval is current-run, test-environment and visible-UI only. API business writes, production writes and a second submit are blocked.
- Required fields and date controls must be deterministically valid before R2 authorization; otherwise fail before consuming the submit allowance.
- Visible client-side required validation after the only click is `write_failed`; a unique list record is `write_succeeded_verified`; success feedback without list verification is `write_succeeded_verification_failed`; absent deterministic signals remain `write_outcome_unknown`.
- A write success followed by verification failure is `write_succeeded_verification_failed`; do not compensate, delete or submit again.
- Teardown releases browser and trace resources only. Created business data is retained with `cleanup_status=not_planned_this_release`.
- RunResultV5是node内pytest阶段与业务write结果的canonical truth，但不拥有PyCharm或人工验收结论。Evidence、report、metrics和experience均为只读投影；PyCharm/人工状态只能由外部AcceptanceResult聚合，不得由RunResult自证或升级。
- A historical unknown write outcome may be diagnosed only through a new hash-bound `ui-test.run-reconciliation.v1` record. Reconciliation is diagnostic-only, keeps the canonical RunResult unchanged and never grants rerun authorization.

## Required Gates

Before write: project config v2, Packet 3.0, Source/IR Schema, migration issue, sensitive scan, Path Plan and `in_sync` checks.

After write/run: scan produced paths and formal references, validate hashes and release status, then close RunResultV5/evidence、commit、receipt、terminal、SessionResult与外部Acceptance闭包。Any stable P0/P1 issue blocks completion.

## Execution Context Governance

### 项目配置和运行记录版本

- 新项目以 [2.4 项目配置](../assets/project-v2.4.template.json) 为模板，设置 `contract_version: 5`、`session_result_contract: v2`。正式入口要求明确选择 runner；R2 批准、阶段预算和写入提交继续独立校验。
- 切换项目的正式入口前，等待使用旧运行时的进程退出，核对原节点 terminal 与回执。旧进程无法读取新版策略。2.3 原配置使用原 Schema 核验；缺少明确决定时，旧模板的串行常量读取为 `legacy-template-default`。
- 2.4 可在项目顶层写入 `serial_constraints` 数组。2.3 可在项目配置同目录放置 `ui-test.serial-constraints.json`，内容为同一数组。每项含 `decision_ref` 与 `scope`。全项目选 `project-environment`，限定节点选 `nodes` 并列出 `node_ids`。执行上下文保存原配置版本、原配置摘要和实际选用的来源与约束。
- 本次执行产生 ExecutionContextV5、RunResultV5、SessionResultV2。原 ExecutionContextV4 和 SessionResultV1 按记录版本校验；2.2 及以前项目执行前仍需迁移。

### 通用 pytest 插件为唯一控制层

- 所有项目通过根 `conftest.py` 显式加载`ui_test_core.pytest_runtime_plugin`。该插件是ExecutionContextV5、AttemptV2、finalization状态和SessionResult的唯一控制层：注册参数、分类来源、绑定node并收集最终pytest阶段结果。项目runtime只消费已验证上下文并返回候选，不得自行识别PyCharm、生成Run ID、授予R2批准或写terminal。
- 普通正式业务run由插件驱动项目finalizer生成RunResultV5/evidence候选，再交给core事务存储。`--ui-pre-submit-only`保留qualification attempt/terminal并由独立QualificationResult表达，但不得生成业务RunResultV5、commit或receipt；不得因缺少业务pending把成功qualification改写为teardown失败。
- 缺失插件加载的收集必须失败。`pytest --trace-config` 可证明加载。

### 来源与批准分离

- `execution_origin` 与 R2 授权决定分离。JetBrains runner 真实入口路径只产生 `pycharm` 来源分类，不独立授予写权限。实际批准由来源策略、risk level、environment、entry scope 共同决定。相应节点还须取得所有适用的显式串行范围。
- 当上述受支持项目策略完整满足并由普通PyCharm Run/Rerun/Debug触发自动R2时，稳定`approval_source`为`pycharm-project-policy`；它表示项目策略对当前node的一次性批准，不是跨run的人工长期授权。
- 非 PyCharm 入口（CLI/CI/Codex）无显式 Run ID 或批准时必须 fail closed，不得使用固定 `manual-run` 回退。

### 指定用例与来源摘要

- pytest 必须显式指定当前 Python 文件或节点。插件从该文件计算 runner_digest，写入上下文；批准与结果关联本轮摘要。
- runner 路径结构匹配即可识别来源；runner 内容摘要变化只记录不阻断（RISK-002），但V3必须记录本次可读的runner内容哈希，进程结束后的Acceptance必须与实际helper文件逐字节读回一致；内容不可读时不得形成V3执行上下文。
- PyCharm helper 进入 pytest 后可能改写 `sys.argv`/`sys.orig_argv`；resolver 还必须校验 `__main__.__file__`。三种入口证据均只在真实文件存在且后缀严格为 `helpers/pycharm/_jb_pytest_runner.py` 时成立，`PYCHARM_HOSTED` 仍只是提示，不能单独授权。
- PyCharm 2025.3 还可能改写 `__main__.__file__`；Windows resolver 因此通过 `GetCommandLineW` 与 `CommandLineToArgvW` 读取创建进程时的原始 argv，但只检查脚本入口位置 `[1]`。后续普通 pytest 参数中的同名路径不得产生 PyCharm 来源或 R2 批准。
- PyCharm helper 会为本地 TeamCity 测试消息协议设置 `TEAMCITY_VERSION`。该单一传输标记不得覆盖严格验证的 JetBrains runner；其他强 CI 标记仍优先，且没有 runner 时 `TEAMCITY_VERSION` 仍分类为 CI。

### 显式串行范围

- 2.4 使用 `serial_constraints`，2.3 使用同目录的 `ui-test.serial-constraints.json` 记录明确决定。`project-environment` 覆盖当前项目环境全部正式节点，`nodes` 按完整 pytest nodeid 集合匹配。每一匹配约束在 fixture 前非阻塞取得；发生占用时显示具体范围、决定引用和“该范围被占用，本次未执行”。操作系统在持有者退出时释放锁。没有匹配约束时可直接执行。

### 两级 Diagnostics/Attempt 边界

- 身份门禁前的失败（无效配置、未指定文件、授权缺失等）进入 diagnostics（append-only），不创建正式 RunResult。
- 通过门禁后创建不可变AttemptV2并按`setup → call → teardown → finalizing`追加事件。普通run只有内容寻址payload、单一原子commit manifest和成功receipt全部闭合后，才可创建唯一`passed` terminal；恢复器只追加`interrupted`或`unresolved`，不得改写历史事件或补写passed。

### 事务化Finalization与进程验收

- RunResultV5与evidence index先进入受控staging，再安装为`objects/<sha256>.json`内容寻址payload；读者只把单一`finalization-commit.json`视为提交点，孤立staging、object或固定旧文件名均不构成提交。
- commit必须先于成功RunFinalizationReceipt，成功receipt必须先于唯一passed terminal。commit前失败不得留下可接受半成品；commit后缺receipt只能记录`status=failed`、`recovery_mode=post-run`，永远不能追认为同进程通过。
- finalizer异常或非法返回必须生成Schema有效的脱敏failure receipt，持久化稳定`error_code`、`exception_class`与`message_digest`，同时向pytest TestReport和TeamCity提供非空`longrepr/details`；不得持久化原始异常消息、私有URL或凭据。
- `pytest_sessionfinish`生成 PytestSessionResultV2，记录预期节点、各节点的实际处置、已有 terminal/receipt 引用及最终 pytest 退出状态；它不得补写passed terminal、修改RunResult或升级业务状态。
- 外部进程控制器先生成PyCharmProcessEvidenceV1，只保留helper路径/内容摘要、真实observed exit及stdout/stderr哈希；PyCharmAcceptanceResultV1只能从实际文件读回生成，并绑定该进程证据、对应版本的 ExecutionContext、terminal、授权、RunResultV5、commit、receipt和SessionResult。只有session exit=0、helper exit=0、无post-run recovery且闭包完整时，`pycharm_integration`和`human_r2`才可为passed。

### 分层完成状态

- pytest阶段、业务write state、finalization、session exit、外部PyCharm/人工验收和整体完成状态不得互相替代。pytest passed不升级业务成功；RunResult/terminal不能自证PyCharm通过；任何非零exit、receipt缺失或post-run recovery均阻断验收；人工A/B真实R2均形成外部AcceptanceResult前整体状态不得为`passed`或`completed`。

### 已接受风险

| ID | 决定 | 复审条件 |
|---|---|---|
| RISK-001 | unknown/unfinished 上一 run 不阻断新 run | 出现重复数据、归因失败或用户撤回 |
| RISK-002 | runner 内容摘要变化不阻断，只记录 | 出现 PyCharm 升级不兼容或来源误判 |
| RISK-003 | Debug 同样自动 R2 | 出现断点误提交或调试事故 |
| RISK-004 | suite 每节点独立 R2，可产生多条数据 | 出现跨节点冲突或测试数据容量问题 |
