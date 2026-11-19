# CR-20261119-019 · 两行定位修复与新版复用

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Issue | #19 |

## Summary

在独立公开项目中复现两行歧义。受影响用例回归成功后启用精确定位版本，由后续独立 pytest 正式运行核验。

## Context And Problem

旧版按所有行寻找复选框。只有一行时目标唯一，出现两行后无法确定应完成哪一项。规格 AC-03 要求保留现场、归因、局部暂停、验证和新版复用证据。

## Sections Changed

scripts-and-validation。asset_repair.py 核验直接与传递依赖、已提交的源用例证据及回退条件。examples/todomvc-repair 提供使用正式执行插件的项目副本与两行源用例。

## Decision And Alternatives

项目自管源保存可恢复的修正版本。外来和归属未明的源在项目内创建适配文件，保留原始字节。候选验证使用独立项目文件、run ID 和浏览器上下文。范围未查清时暂缓启用。

## Detailed Change

限定版本先经 component.ready 和 script.complete 对应的源用例回归，再由 AssetCatalog 按预期修订发布。回退核验当前范围、暂停状态、快照与回归证据。原子 V5 使用正式 pytest 阶段结果、真实 attempt、项目的阶段预算及当次截图。每步使用明细带摘要，启用决定关联失败及回归的 V5 摘要。

## Impact Analysis

改动限于项目内共用的修复辅助函数和独立两行示例。主项目 A 的 v1、源用例、经验文件未参与本票写入。

## Safety And Privacy

只运行公开 TodoMVC，通过正常界面新增和勾选。每个运行独立上下文，限三个阶段。失效定位只消耗两次新增，站点请求限界面自然触发的已审查静态 GET。

## Risks And Follow-up

实际浏览器验收覆盖自管定位修复，外来源与归属未知时的项目侧适配及回退有本地定向测试。独立样例的绑定表只有一个受影响用例。

## Validation Evidence

源用例在 [local artifact] 中原样运行。运行目录 runs/<run-id>/finalization/finalization-commit.json 链接 V5 和步骤 use.json。候选验证副本为 [local artifact]。

| 运行 | V5 摘要 | 结果 |
| --- | --- | --- |
| OLD19V5 | 3ffdcfd16a7c96a28c290032453365b92bb2f405a7c1220c1a1a1af8d7f0cccc | v1 命中 2，点前停止，2 个新增，剩余 2 |
| TRIAL19V5 | 03f6fea3c00aa909e30bec1444606440b6a2f19134051716c80e9d262274bae8 | v2 命中 1，仅指定项勾选，剩余 2→1 |
| USE19V5 | 4c486dda8ecede8d5eaed437efc03adca1872d9c72d3adaf4d5f9a3f62b06d9a | 正常入口读取已启用 v2，再次通过原断言 |

5 项定向回归通过。.scratch/reuse19/verification-01/result.json 独立复核三次 V5、源码及实现哈希、版本、暂停与依赖。V5 接入前的探索运行保存在独立的 -01 与 -02 项目副本。
