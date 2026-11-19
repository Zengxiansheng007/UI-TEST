# CR-20261119-018 · 固定用例资产版本与并发决定

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Issue | #18 |

## Summary

项目正常 pytest 节点在用例开始固定资产目录和传递依赖。每一步执行前按当前作用范围复查暂停。

## Context And Problem

逐步重新发现目录会使后续步骤选到运行中新启用的版本。原目录缺少可比较的修订和原子发布操作。

## Sections Changed

scripts-and-validation、examples/todomvc/project_runtime.py 及对应测试。

## Decision And Alternatives

复用现有跨进程文件锁、项目静态发现、作用域检查和 V5 终态回执。零修订沿用既有项目文件。新修订按摘要存放，清单指针在内容落盘后原子替换。

## Detailed Change

AssetCatalog.publish 和 pause 持锁比较 expected_revision。旧写者收到当前修订号，必须重新读取清单并重新判断。选择明细记录固定版本及直接和传递依赖。当前页面从该版本的恢复文件加载定位器。事件身份包含运行、步骤、尝试及序号，分歧内容进入独立冲突文件。

## Impact Analysis

已在运行中的用例沿用固定目录。后续用例使用最新完整清单。源用例及其写预算继续控制业务动作。

## Safety And Privacy

故障和发布只作用于隔离项目副本，沿用可见公开页面和既有被动网络记录，重投递只读回或核对既有证据。

## Risks And Follow-up

中断测试使用进程退出覆盖发布前的窗口。本次覆盖本机文件系统进程中断。

## Validation Evidence

.scratch/reuse18/REUSE18-PUBLISH-02.log、REUSE18-PAUSE-01.log 及 verify-01/result.json。发布中运行仍使用定位器 v2，原断言通过。下一次运行使用 v3，COMPLETE 的暂停阻断勾选，提交计数为 1。两个原始终态回执重投递均为 duplicate。首次运行 REUSE18-PUBLISH-01 的缺陷及其失败证据已保留。19 项定向检查覆盖双进程竞争、清单切换前退出和启动新进程、事件冲突与终态事务。

