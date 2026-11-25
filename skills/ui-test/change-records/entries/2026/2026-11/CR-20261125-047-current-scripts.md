# CR-20261125-047 · 按中文用例名查当前脚本

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | 5bb2c13 |
| Requirement | #47, P1-AC-01 |

## Summary

中文项目目录按业务名、用例及分支列出当前脚本，提供节点及其可核实的生效来源。

## Context And Problem

已发布脚本只有按标识列出的生效记录，未发布入口的执行时快照无法表明当前选择。

## Sections Changed

项目刷新将生效发布或手写入口声明投影到 SQLite 与 HTML。盘点记录已确认的手写脚本使用方。

## Decision And Alternatives

保留已有发布指针；未发布入口使用项目明确声明和源码节点核验。同分支声明冲突保留待核状态。

## Impact Analysis

历史目录和尝试继续显示原始绑定。历史 SQLite 可按原来结构只读打开，刷新时补建当前用例表。

## Validation Evidence

test_current_scripts.py 覆盖同一脚本的多个节点、改名、缺节点、缺件与声明冲突；实际 CLI 验证两类当前入口。

## Safety And Privacy

声明限制在本项目公开 Python 文件。目录构建只解析源码。

## Risks And Follow-up

动态生成的测试节点需要可核实的运行依据；源码中无法定位的节点标记待核。
