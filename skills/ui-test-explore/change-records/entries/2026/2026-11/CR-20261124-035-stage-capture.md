# CR-20261124-035 · 运行中采集步骤截图

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test-explore |
| Baseline | a008d7d |
| Source | UI-TEST #35 under #31 |

## Summary

两阶段执行在业务状态可见时采集像素并保留多图引用。

## Context And Problem

仅在报告生成时读取记录无法追溯已消失的回执或已清空的输入字段。

## Sections Changed

更新脚本、运行用例、使用说明及回归测试。

## Decision And Alternatives

使用执行用例已有的浏览器上下文和观察或断言，按实际业务时点截屏。

## Impact Analysis

探索记录当时页面观察，正式收尾使用同次 V5 的相对引用与哈希，沿用共用发布器。

## Validation Evidence

回环受控写用例 test_staged_submit 通过，两阶段输出分别见 35/formal2 和 35/midscene。tests/stage_capture.test.cjs 与 test_stage_capture.py 用原图像素及视口/整页尺寸核对脱敏。

## Safety And Privacy

默认遮挡密码及显式敏感区域，调用方配置应用特有选择器。公开页面与模型资格验收另见 #38。样本只使用虚构字段。

## Risks And Follow-up

浏览器异常退出可能导致缺图。保留缺图原因和已有记录。
