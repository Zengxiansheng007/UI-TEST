# CR-20261125-046 · 阶段原件与关联报告

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Scope | core-skill-md, scripts-and-validation |
| Baseline | c02377c |
| Requirement | #46 · P1-R08 · AC-01、AC-07 |

## Summary

正式阶段在启动时固化明确来源，目录按该来源更新反向链接，正式报告读取已记录的来源。

## Context And Problem

工程师需从已交付阶段报告末尾打开执行时版本、证据及有来源的上下游阶段。

## Sections Changed

正式阶段在启动时固化明确来源，目录按该来源更新反向链接，正式报告读取已记录的来源。

## Decision And Alternatives

来源只在阶段第一次启动时记录。已交付的探索报告通过稳定目录锚点读到随后建立的一个或多个关联。

## Impact Analysis

两阶段沿用已有生成器和正文截图。报告只读取阶段原件。

## Validation Evidence

两用例探索与多个正式阶段的受控离线运行，校验原件、独立与未知来源、反向目录以及截图回归。

## Safety And Privacy

项目内相对引用可在离线目录中打开。显示文本转义，校验关联阶段身份。

## Risks And Follow-up

历史缺证按未知展示，保留存量文件。
