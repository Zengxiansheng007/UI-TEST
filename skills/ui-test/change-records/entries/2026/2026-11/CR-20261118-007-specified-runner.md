# CR-20261118-007 指定用例启动

项目 2.3 使用指定 pytest 文件或节点，运行时直接计算 runner_digest。ExecutionContextV4、Approval V3、attempt 和 V5 提交前校验关联本轮上下文、授权、快照与事务。

回归入口为 assets/fixtures/specified-runner/local_case.py::test_single_submit；本机回环受控页一次可见提交，运行目录由 CONTROLLED_UI_EVIDENCE 提供。

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | .scratch/t01/source-sha256.txt |

## Summary

指定 pytest 文件或节点即可进入受控执行。

## Context And Problem

旧入口要求预登记 active 身份及固定 runner 目录，阻断了已获授权的 POC 用例。

## Sections Changed

core-skill-md, references-and-assets, scripts-and-validation

## Decision And Alternatives

执行时读取实际文件计算来源摘要，并在提交前独立校验本轮授权与证据引用。

## Detailed Change

项目 2.3、上下文 V4、批准 V3 和 attempt 记录本轮来源。V5 校验授权、上下文、快照、节点和事务关联。

## Impact Analysis

新入口要求显式选择文件或节点，旧配置保留审计用途。

## Validation Evidence

171 项定向回归通过。可见 Chrome 运行一次提交，证据见 .scratch/t06-evidence.md 和 .scratch/t06-final-regression.log。记录格式校验见 .scratch/t06-record-validation.json。

## Safety And Privacy

验收使用回环页面和本地夹具。仅浏览器自然发送业务请求。

## Risks And Follow-up

本机回归日志曾打印 Windows 0xc0000008，最终退出码为零。外部 PyCharm 和人工验收未执行。
