# CR-20261125-042 · 项目运行目录与按尝试查询

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | fd90aab |
| Requirement | #42, P1-R04、P1-R05 |

## Summary

项目运行目录与按尝试查询。

## Context And Problem

多用例共用一份阶段报告，需要独立定位每条尝试及对应证据。

## Sections Changed

正式执行从封存 V5、会话节点和事务清单提取阶段、分支、尝试与原件。项目刷新读取 stage.json 生成 runs.sqlite3 和离线 index.html。

## Decision And Alternatives

目录展示与 SQL 查询复用相同登记行；按项目时区的开始日查询。缺证时间、版本保持未知。

## Impact Analysis

历史报告保留原件。开始日未知的历史阶段可按其他条件找到。

## Validation Evidence

见 #42 的受控双阶段样本、跨午夜筛选及独立验收记录。

## Safety And Privacy

项目内相对引用保留原始位置，离线目录使用本地文件。

## Risks And Follow-up

登记时点和写库中断恢复由 #45 验收。实际执行版本的绑定由 #44 验收。
