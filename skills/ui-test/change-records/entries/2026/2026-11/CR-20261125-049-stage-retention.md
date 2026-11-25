# CR-20261125-049 · 阶段保留与预演

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | 2093b42 |
| Scope | core-skill-md, scripts-and-validation |
| Requirement | #49, P2-R02–R04 |

## Summary

工程师可在项目首页找到手动预演命令并打开历次清单。每阶段显示保留理由、参与处置的文件和继续使用它们的阶段、步骤或资产。

## Context And Problem

高频分支可能掩盖低频分支的现场；同一次运行可能有多条用例、重复尝试或多个步骤共用一张图。

## Sections Changed

项目治理程序新增 `preview`。清单以可靠结束时间和分支的实际执行记录判断整阶段，支持按项目配置天数、最近次数和人工保护。

## Decision And Alternatives

候选、留用副本和拟释放路径从同一批盘点事实产生。普通手动请求独立生成清单，带命名空间的请求标识可复用已交付的同一清单。

## Impact Analysis

只有多方共同参与处置且无继续使用方的工作副本可拟释放。未执行用例不计次数，重试只占一个阶段。

## Validation Evidence

`test_retention_preview.py` 覆盖跨阶段与分支排名、多用例整阶段保留、失败、缺件、人工保护、共享副本和重复请求。项目入口可离线打开 HTML。

## Safety And Privacy

只在项目治理目录写清单及刷新项目目录视图。阶段报告、脚本、证据与归档目的地保持原状。

## Risks And Follow-up

预演清单等待审批，实际执行必须重新核对批准范围与当前事实。
