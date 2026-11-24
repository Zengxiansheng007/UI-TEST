# CR-20261124-135 · R0 正式断言与零提交收据

| Field | Value |
|---|---|
| Status | validated |
| Target Skill | ui-test |
| Change Type | fixed |
| Scope | core-skill-md, references-and-assets, scripts-and-validation, safety-and-governance, downstream-and-handoff |
| Source | UI-TEST #31, #35, #38, AC-04 |
| Baseline | a008d7d0c00cf43d81e221ef00ee6d895600c74c, skill tree e49eae11720c6fb4acfb819a67b2e64d27a720f3 |
| Author | Codex |
| Related Records | CR-20261124-032 |

## Summary

公开查询用例可将 pytest 观察到的成功或失败断言作为本次正式事务提交。V5 记录零次提交，阶段报告可以按原始 V5 汇总。

## Context And Problem

旧版只读节点的终态使用 not_applicable_read_only。V5 成功条件要求已验证写入。混合批次的 R2 标志也会出现在只读节点上下文中。

## Sections Changed

SKILL.md 给出项目接入示例。pytest_runtime_plugin 处理显式启用的只读事务。run_evidence_linker 与 V5 schema 约束零写入结果。pycharm_acceptance 校验人工 R2 成功时必须具备已验证写入状态。

## Decision And Alternatives

项目用 r0(formal_result=True) 启用已有事务钩子。未启用的 R0 节点继续保持旧版执行上下文与终态语义。资格验证沿用原流程。

## Detailed Change

适配器从 attempt 已封存的上下文生成包含 runner、项目配置、用例、尝试和零次提交的只读边界，保存在本次运行目录。V5 引用其路径与摘要。插件从当前 attempt 重新派生并核对该边界。R2 继续走原有批准检查。显式 R0 的通过和失败结果均使用 not_attempted、0，并禁止阶段写入预算。

## Impact Analysis

正常控制器和报告继续读取已提交的 V5 和 receipt。现存 V5 可以按原 schema 语义校验。历史资格验证和无事务只读诊断保留原行为。

## Validation Evidence

证据在 c31-evidence/35/readonly。red.log 记录旧上下文误继承批次标志。red-r2.log 记录旧人工验收器缺少写入状态判定。verified.log 包含正常 pytest 收尾、失败断言、绑定篡改、V5/收据与 R2 回归。受控断言和报告来自本地 pytest 子进程。105 项通过，5 项因可选 xdist 或浏览器开关跳过。standalone.log 另核对单条成功只读运行的真实退出码与报告。首次包校验受基线 #34 记录影响；并入既有 a6770ec 后，skill-validation-candidate.json 三档发现均为零。

## Safety And Privacy

本地回归只使用夹具。敏感值检查仅报告匹配数。报告生成只读取原始事务。

## Risks And Follow-up

#38 用已批准的公开页面包核验 A 的一次提交与同一阶段 B 对目标行的零写入读取。变更记录中的受控输入仅用于回归。
