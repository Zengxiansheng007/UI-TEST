# CR-20261127-061 · 历史运行查询

| Field | Value |
|---|---|
| Status | applied |
| Baseline | 5ec3a37 |
| Target Skill | ui-test |

## Summary

按 #61 将历史运行的登记、重放和查询移交 run-catalog。

## Context And Problem

按用例找回旧运行时，需区分执行所用脚本与项目当前启用脚本。旧运行登记命令与导入路径有现有调用者。

## Sections Changed

references-and-assets, scripts-and-validation.

## Decision And Alternatives

查询从项目重放索引，沿当次尝试记录内的绑定取文件与哈希。多个阶段同时命中时列出候选。

## Detailed Change

迁移阶段事件、SQLite 注册、正式运行登记、阶段交付登记和 HTML 阅读器到 run-catalog。保留主 Skill 的原导入路径，使用所选套件加载唯一实现。

## Impact Analysis

影响探索发布、正式执行收尾、项目目录和归档索引刷新。已有阶段 JSON 和数据表格式继续可用。

## Validation Evidence

新入口测试使用可替换的当前脚本与保留的 V1 快照，同时核对公开旧命令、原件与标识查询、重复刷新、多义与缺件。阶段事件、项目盘点、归档历史和当前脚本回归覆盖兼容调用。独立 CLI 验证读回历史 V1、未知标识及旧命令的项目目录链接。

## Safety And Privacy

测试在本地隔离合成项目运行。查询校验项目内相对路径及版本绑定，使用 SQLite 参数查询。

## Risks And Follow-up

整套安装与新对话入口验收由 #74 覆盖。
