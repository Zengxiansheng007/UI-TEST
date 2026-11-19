# CR-20261119-015 · 用例资产选择

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Issue | #15, AC-04 selection |

## Summary

项目从当前源用例和运行授权解析步骤可用版本，记录各候选去向。

## Context And Problem

原查询仅接受资产 ID。TodoMVC 只在 OPEN 用环境字段核验绑定。变更前项目运行时摘要 7cd7446c14e64602ebedfcd0a81cec21193b87070f0dfb488e4f8326bb4e2ae1，查询模块摘要 65c812340c715d746977a214bdccdf46f8ea99d9d7f19adcc593df42318bdf68。

## Sections Changed

scripts-and-validation，examples/todomvc 的运行时与项目声明。

## Decision And Alternatives

沿用静态发现、项目启停记录、恢复文件和原 pytest 节点。源步骤硬绑定优先。无硬绑定时检查同项目同环境专用声明，再考虑显式共享声明。同级可用版本冲突时记录全部 ID。

## Detailed Change

select_asset 保留项目组、产品、系统、模块路径、功能、checkpoint、环境、风险与用例步骤身份。递归检查依赖、启停范围、版本来源、前提及当前允许的副作用。项目运行时在 OPEN、READY-COMPLETE 与 COMPLETE 生成选择记录。READY-COMPLETE 允许在无可用组件时按原断言只读检查当前行，单独记录本次探索。

## Impact Analysis

保留 applicable 查询契约、原步骤、断言及写前预算。当前用例没有 checkpoint 绑定时记录 null。公开示例已声明所属项目。缺少明确归属的旧资产在自动选择时需补核归属。

## Safety And Privacy

公开 UI 运行沿用可见浏览器与原网络限制。决策证据保存范围、版本及原因。未引入凭据输入或主动业务接口。

## Risks And Follow-up

读取版本后检查恢复字节。跨步骤版本固定、原子版本发布分别由后续相关工单验证。

## Validation Evidence

新增选择测试 4 项，联合原静态发现 4 项通过。红测先观察到选择接口不存在，后续无授权副作用反例先观察到意外允许探索，修复后通过。Root 独立运行 REUSE15-ROOT-001，原 pytest 节点 1 passed；提交的 V5 包含五步通过与两次提交，OPEN 选择显式绑定，READY-COMPLETE 与 COMPLETE 使用专用版本。


隔离副本硬绑定环境不符，REUSE15-HARD-01 在 OPEN 报出 hard_binding_unavailable，V5 确认提交 0、后续跳过且没有网络事件。另一个副本停用 READY-COMPLETE 专用组件，REUSE15-FALLBACK-01 从同一 pytest 节点通过，独立探索收据进入 V5 步骤链接，原五步通过且预算为 2。三个结果由 .scratch/reuse15/verification-01/result.json 的独立读取检查通过。--require-change-records 返回 validated-candidate，P0/P1/P2 均为零。变更源码的常见凭据模式扫描未命中。

自查新增依赖步骤范围反例。补核传递依赖自己的 steps，并在项目声明核准 READY-COMPLETE 使用 locator.rows。选择回归 4 项通过。修订后正常节点 REUSE15-ROOT-002 通过，耗时 10.61 秒；.scratch/reuse15/verification-02/result.json 对新正例和仍适用的原两项异常证据分别核验，3/3 通过。

活动 SKILL.md 的执行指南已使用 select_asset。对应 core-skill-md 及 references-and-assets 台账已关联，旧活动说明和 source-baseline.json 留在 .scratch/reuse15/baseline。正式包共 252 个文件，排除 Python 和 pytest 临时缓存，活动 SKILL.md 摘要 f7fc91e3eb7918e80f8107d3df75943e71eb8e8dd0f06520d06b7b958a5d2292。维护者批准同步活动基线后，原失败的注册表基线检查与发现、选择回归共 9 项通过。

扩大回归排除 4 个非 TodoMVC 可见站点夹具。首轮 485 项中 457 通过、28 失败。在机器锁定依赖及独立短路径重跑上述 28 项，26 通过。余下两项为活动基线摘要和 #17 的旧暂停用例断言，各自修订后按失败项单独验证。各轮原始输出保留在 .scratch/reuse15。
