# CR-20261125-044 · 执行时版本绑定

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | dda59a9 |
| Requirement | #44 · P1-R06 · AC-04、AC-05 |

## Summary

正式入口在 setup 保存实际节点、脚本与项目依赖。中文目录与 SQLite 提供同一批版本引用。

## Context And Problem

脚本更新后仍须从旧尝试打开实际入口、测试节点与执行所需的共享文件。

## Sections Changed

正式入口在 setup 保存实际节点、脚本与项目依赖。中文目录与 SQLite 提供同一批版本引用。

## Decision And Alternatives

引用完整且可核验的发布，其余文件按内容摘要固定和复用。只从执行原件投影历史版本。

## Impact Analysis

当前入口由生效指针决定，旧尝试保留自己的版本。兼容缺少绑定的历史结果。

## Validation Evidence

正式 pytest 事务、双版本探索样本、发布切换、SQL 和 HTML 反查。

## Safety And Privacy

在项目授权目录内写入本地文件并校验路径。历史缺证显示缺口。

## Risks And Follow-up

动态加载的探索依赖由 planSource 及 dependencies 补足。
