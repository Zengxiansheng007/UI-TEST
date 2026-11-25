# CR-20261125-048 · 项目产物盘点与使用方

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | dda59a9 |
| Scope | core-skill-md, scripts-and-validation |
| Requirement | #48, P2-R01, P2-R04 |

## Summary

项目首页可打开按类型汇总数量和字节数的盘点页。文件保留多个阶段、分支、尝试、步骤及在用资产的引用。

## Context And Problem

共享截图可能位于临时目录，且多条用例可能引用同一路径。只有少数历史批次应取得处置资格。

## Sections Changed

治理入口写出 JSON 和离线 HTML，复用阶段事件、脚本快照及项目目录。Skill 正文给出命令、允许的根及点名历史批次的配置。

## Decision And Alternatives

按产生引用时的基准目录解释记录。点名批次与旧记录身份冲突时，相关文件保留在仅盘点范围。盘点与目录刷新共用数据库投影。

## Impact Analysis

中断阶段从开始和尝试事件读回。已封存阶段保留报告与当时的入口、依赖。只有历史目录的项目仍可生成盘点。

## Validation Evidence

`test_artifact_inventory.py` 检查阶段证据、缺件、旧批次身份、共享资产、历史版本及中断事件。离线浏览器从项目首页打开盘点并查看指定历史报告。

## Safety And Privacy

遍历前排除私有区；配置的根和原件必须符合项目路径边界。盘点可在没有归档介质时执行。

## Risks And Follow-up

缺件与待核引用保留阶段和步骤信息，供后续预演和归档核验读取。
