# CR-20261119-016 · 探索经验和脚本复用

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Issue | #16 |

## Summary

将实际脚本使用和原业务断言绑定到当前运行，通过独立重跑形成项目内启用决定。

## Context And Problem

项目已能选择脚本，完成步骤的 V5 曾仅链接选择明细。原经验查询保存建议，缺少当前版本的实际执行与独立批准依据。

## Sections Changed

scripts-and-validation，TodoMVC 的 pytest 适配器、脚本声明和项目入口。

## Decision And Alternatives

沿用正式 V5、当前页面及源用例预算。经验候选和限定决定由项目文件持久保存；机器上的全局 Skill 保持原部署。

## Detailed Change

项目适配器确认声明的输入、动作和副作用，使用冻结版本和既有页面，记录脚本执行、原断言、实际计数及采用策略。strategy_learning 从已提交的 V5 核验使用摘要、步骤、运行、构建和证据。普通运行仅消费已启用经验。显式试验运行可在原授权下验证同范围候选。成功和失败分别形成采用或排除某项策略的证据。

## Impact Analysis

原 pytest 节点、原编译用例、阶段预算及公开站资源限制继续生效。每个经验限定到源用例、步骤、八项业务范围、构建和资产版本。未识别的脚本契约在写入派发前停止。

## Safety And Privacy

经验只保存经项目适配器审查的结构化预期、观察结果、动作类型、范围及证据引用。原始输入、页面正文及网络正文不复制进经验。

## Risks And Follow-up

项目适配器为每种可执行策略实现对应动作。未实现的策略仍可保存为候选。

## Validation Evidence

红测先观察到经验模块缺失。针对负经验的第二轮红测观察到策略选择器缺失。实现后候选和选择回归共 6 项通过。

公开站 REUSE16-OBS-001 形成候选 6b601c8c2dfefbd55bf54f7c001701f7aed100b0ed7e0739801da95776a1085b。独立运行 REUSE16-TRIAL-001 通过原业务断言后启用。A 端的最终正常运行 REUSE16-A-002 进入 script.complete@1，SHA-256 为 804d6ef1132ce54b4548521670034e1c84c26f91a0c6ad1a9bd48f7a8233b555。当前用例新建待办从 1 item left 变为 0 items left，勾选成功。

由 examples/todomvc/asset-paths.json 中 TODO-P0-002 的 branch_root 进入 runs/REUSE16-A-002。其 finalization/finalization-commit.json 指向 finalization/objects/a0a7d02e6b51ffb85f985419effef7f29784bbdbc0e931067665faedd3fba3c6.json；COMPLETE 步骤关联 reports/script-use.json、截图及选择记录。

隔离项目 [local artifact] 的旧脚本在 NEG16-OBS-001 观察到目标数量 2。该次只发生新增，完成提交预算保留为结果未知。独立的 NEG16-TRIAL-001 排除失败策略，改为按源文字限定当前行，通过后批准。普通运行 NEG16-USE-001 再次从正式文件找到该负经验，使用同版脚本，原断言和 1→0 通过。每个运行保留独立的提交与使用记录。

runtime-verify 在 .scratch/reuse16/verification-01/result.json 记录三项通过，分别复核正经验使用、负经验排除和原失败预算。各正常运行实际观察一次新增、一次勾选。--require-change-records 返回 validated-candidate，P0/P1/P2 均为零。
