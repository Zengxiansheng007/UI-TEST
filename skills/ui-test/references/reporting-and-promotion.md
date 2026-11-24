# Reporting And Promotion

Read this reference when creating reports, reviewing run quality, or deciding whether to generate stable regression assets.

## Business Test Report

Use a Chinese HTML filename and include:

- scope, environment, role, and safety boundary;
- requirement/test-point coverage;
- normal, abnormal, boundary, permission, and downstream results;
- expected versus actual results;
- final route/state and strongest business evidence;
- defects, reproduction steps, severity suggestion, and evidence links;
- exclusions and unverified claims.

Do not include passwords, tokens, cookies, full private payloads, or unnecessary personal data.

## Agent Execution Quality Report

Use a separate Chinese HTML filename and include:

- Midscene attempted/verified pass ratio;
- model calls, latency, timeouts, retries, and repeated failures;
- false positives and false negatives;
- Playwright fallback count and reason;
- evidence completeness and redaction result;
- issue classification;
- repairs applied and re-run outcome;
- remaining risks and recommended upstream changes.

## Promotion Gates

Promote to Playwright/Hybrid regression only when all are true:

1. the requirement and expected result are stable enough to automate;
2. deterministic verification passes on repeated runs;
3. no unresolved business, requirement, access, or environment issue remains;
4. test data can be prepared and cleaned safely;
5. locators use stable contracts or a documented semantic fallback;
6. evidence is complete and reproducible;
7. the flow has bounded runtime and retry behavior;
8. maintenance ownership is known.

Choose:

- **Playwright** for stable, critical, high-frequency paths.
- **Hybrid** for changing UI with stable business checkpoints.
- **Midscene exploration only** for volatile or poorly specified flows.
- **Do not promote** when success depends on one shared environment run or unverifiable model judgment.

## Repair Gate

| Change | Gate |
|---|---|
| wait condition, locator scope, evidence index, report formatting | automatic |
| exploration wording or low-risk assertion clarification | automatic with re-run |
| test-data creation, update, cleanup, or business action | explicit confirmation |
| deletion, publishing, payment, permission change, production mutation | forbidden unless narrowly and explicitly authorized |
| weakening/removing an assertion to obtain green status | forbidden |


## 正式执行结束后的交付

正常 pytest 正式会话收尾时读取该会话的节点、尝试及已提交 V5，并输出一个可打开的阶段报告链接。
Codex 调度由最外层批次负责发布，同一批次的所有子会话汇总到一份 HTML。
将输出的 `UI-Test stage report` 链接直接交给工程师。报告目录同时包含 execution-summary.json 和 evidence-index.json。
这条链路需要 ui-test 与 ui-test-execution-report 两个并列技能包。报告生成失败时记录错误，按已归档结果重试交付。


### 正式步骤现场留图

项目运行时在现有动作和断言的边界调用 `ui_test_core.stage_capture.capture_step(page, step, context=context, run_root=run_root, point=..., object_ref=..., observation=...)`。传入本次执行上下文字典和当前 V5 步骤。核对输入后用 `pre_submit`，观察到明确业务回执时用 `receipt`，结果断言后用 `final`，等待终止时用 `timeout`。同步返回最终结果的页面可只记录一次实际结果。查询使用 `query`；额外核对使用 `author` 并传入 `reason`。同一步可多次调用，finalizer 将步骤及相对 evidence_refs 原样绑定本次 V5。

通过 `mask_selectors` 传入页面内需要遮挡的敏感字段、文本及图片选择器。默认遮挡密码、带 data-ui-sensitive 标记的区域、支付卡号及一次性验证码字段。对象标识、观察及理由使用已脱敏摘要。完整视口为默认，明确跨屏核对时传 `full_page=True`。

同一尝试中的截图以对象、观察时点和业务状态归组。同一动作留下多图时，显式传入相同的 `object_ref`、`point`、`state_ref`（默认用 `observation`）；区分同类事件的多次发生时传 `moment_ref`。作者实际核对画面后可用 `preferred` 指定本组代表图。能读出对象与状态的图标 `support="direct"`（默认）；只提供上下文的图标 `support="context"`，保留在索引。只有回执本身满足用例目标且画面足以证明时，才给该图填写 `final_goal`，记录具体目标。后续状态变化另行记录。
