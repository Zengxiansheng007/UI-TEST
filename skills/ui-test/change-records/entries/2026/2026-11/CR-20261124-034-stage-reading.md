# CR-20261124-034 · 阶段报告离线审阅

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Change Type | changed |
| Source | #31, #34 |

## Summary

UI-TEST #34，基线 ec740c8，ui-test 树 6f9c065a863bebb82c519d421fc7b3924df582bd。关联 CR-20261124-032。

## Context And Problem

阶段报告的目录与步骤图片需要让审阅者直接核对关键状态。

## Detailed Change

正式会话的阶段投影原先忽略步骤截图，报告无法直接定位关键节点。正式适配器从已核验的 V5 读取本步骤已引用且具摘要的相对图片路径，解析后限定在本次运行目录。共用生成器在步骤内常显关键大图，将同一步的普通图放入一个原生折叠区域，目录链接指向稳定的本页锚点。逐图嵌入已有查看器，适配器和生成器均只读归档。原有单用例命令行沿用其详情布局。

## Validation Evidence

受控本地只读页的正式 pytest 收尾交付了一份实际包含三步的阶段报告。V5 报告的期望失败反映 A-17 待审批与预期已通过的差异，提交数为零。空目录离线 Chromium 验证用例与关键节点跳转、普通开关隔离、大图适宽、原始尺寸、缩放和 Esc 后焦点。普通图 1080×650，指定整页图 1080×1088。检查记录为 c31-evidence/34/offline-check.json。该样本不承担公开页面验收。


## Sections Changed

正式结果的图片引用、阶段报告步骤布局、图片查看器与对应测试。

## Decision And Alternatives

复用单文件查看器，直接展示关键图，将同一步的普通图放入一个折叠区域。

## Impact Analysis

新生成的阶段报告使用此布局，既有报告继续按原文件阅读。

## Safety And Privacy

生成器读取本次运行目录内已核验的截图，原图作为离线资源随报告交付。

## Risks And Follow-up

正式公开页和探索报告的端到端验收见 #38。
