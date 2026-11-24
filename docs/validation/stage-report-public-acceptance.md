# 阶段报告公开页验收 · #31 / #38

2026-11-24，产品提交 `9845561cf6ba1d0aeb20b080aa7a185e78912a9b`。目标为 Playwright 提供的[公开 TodoMVC 测试页](https://demo.playwright.dev/todomvc/#/)。批准的运行包 SHA-256 为 `3156006204365419466a24c50210741534b52620810ada6610e88e6765937160`。下表中的相对位置均以本地专项验收目录 为起点。

| 真实交付 | 阶段报告位置 | HTML SHA-256 |
| --- | --- | --- |
| Midscene 探索 | `38/midscene/PUBLIC-38-EXP/report.html` | `26e9cf6ba47680de12da6892f2e2648de93e00f0a21fe1a47bc658b9b859171e` |
| 正式 Playwright | `38/formal-live/task.json.reports/63a9c9b0a0e13c0118df5f16/report.html` | `34c0589e9749b6c5d4813d10a38040633e77e929855a7a5865f779b2da0841c3` |

## 实际运行及业务证据

真实探索、正式执行及其首次归档复生使用 `9845561`。独立单例 CLI 的输出目录隔离修复随后合入 `1ea16bf446b6bd5d4aa830e8d532d72bec9043d9`。在该提交上再次只读复生两阶段原归档，仍得到与真实交付相同的 HTML 字节，详见 `38/archive-check-cli-fix.json`。

探索在新浏览器上下文中使用本机 PlaywrightAiFixture。模型先确认标题、输入框和空列表，再在 B 中确认新待办未勾选及剩余计数。A 填写 `Stage report sample`，按一次 Enter。页面随即显示同名待办、空输入框和 `1 item left`。B 在同一上下文中读取该行。探索记录为 A、B 均 `observed`。模型观察、原生诊断和报告分别保存在 `38/midscene/PUBLIC-38-EXP/observations.json`、`38/native-public/` 及表中 HTML。

正式批次 `PUBLIC-38-FORMAL` 从空上下文开始，使用项目 `codex_dispatch.py` 的默认串行入口。调度器等待 A 子进程结束，再启动 B 子进程。B 的新上下文只载入 A 实际生成的同源 `react-todos` 单行存储。A 的 R2 授权与提交计数均为 1，B 的 R0 只读边界与提交计数均为 0。两次终结事务均提交，各自 V5 均为 `passed`。A 的可见列表结果同时证明回执与最终目标。该页面没有观察到独立的后台处理状态。

每个阶段各有五张 1440×900 视口图，覆盖空列表、作者指定的页面标题、填写后的输入框、新增结果和只读查询。执行侧已逐张核对归档字节摘要及 run、case、attempt、step 身份。浏览器请求记录仅含 TodoMVC 的 GET 页面和静态资源。运行包、调度任务、V5 对照结果和网络明细分别见 `live-scope.json`、`38/formal-live/task.json`、`38/formal-live/delivery-crosscheck.json`、`38/exploration-traffic.json` 和 `38/formal-live/{A,B}-page-requests.json`。

## 父规格验收记录

| 验收 | 证据来源及核对内容 |
| --- | --- |
| AC-01 | 两个真实阶段各交付一份带 A、B 的 HTML。探索收尾时先交付第一份，正式调度退出时另交付第二份。 |
| AC-02 | 将探索摘要对照当次 observations，将正式摘要对照两个原始 V5 和提交收据。两阶段均调用通用 `publish_stage_report`。已审计专项入口的范围和历史固定打包器见 `33/acceptance.md`。 |
| AC-03 | 真实报告中均有 A 的普通空列表步骤、三个关键步骤以及 B 的只读关键步骤。目录定位与展开交互由下方独立审阅记录补证。 |
| AC-04 | A 的提交前截图可读到完整合成标题。行出现、输入清空和剩余计数证明提交后的结果；B 提供未勾选行及计数。作者节点的理由为通过标题核实操作页面。 |
| AC-05 | 公开页提交后的同一状态证明回执及最终目标。受控补测 `36/verified.json` 另含 A-17 与 A-18、指定且直接支持目标的代表图、等价图索引和“已受理→处理失败”两个可区分的状态。 |
| AC-06 | 真实阶段各有五张完整视口图。受控夹具 `34/offline-check.json` 验证 1080×650 视口和 1080×1088 整页，经隔离 HTML 内嵌图片读取。真实两份交付的阅读操作见独立审阅记录。 |
| AC-07 | 两份真实报告的图片均已核对原始步与尝试。`38/archive-check.json` 记录了从两份真实归档复生到临时目录的结果，两份 HTML 与原交付逐字节一致，77 个原始文件摘要保持一致，网络及启动进程的尝试均为 0。探索发布只重定向输出位置。受控归档另见 `37/verified.json`。 |
| AC-08 | 公开页两阶段均顺利完成。受控补测 `37/verified.json` 及其所列正常阶段报告覆盖失败、阻塞、跳过、未知、未执行、缺图和重复尝试。可逐项查看第一次尝试与第二次尝试的实际记录。 |

## 独立审阅结论

未参与执行和生成器实现的审阅者先离线打开两份交付 HTML 的等字节副本，再对照原始记录。AC-01 至 AC-08 均通过，其中异常与多次尝试由注明来源的受控材料覆盖。原始结论位于 `38/independent/acceptance.md`，SHA-256 为 `1dace4ee4be4b92ccdcaf79e9a49e1b8d291b6112b339f90271b8a663fe59815`。

审阅者从两份报告各自的六个目录链接进入目标，看到四张常显关键图和一个默认收起的普通截图面板。打开普通图和关键图后，原始尺寸均为 1440×900；放大至 400%，按 Esc 关闭，焦点回到触发按钮。两个隔离目录各只有一份 HTML，各自只请求自身。两例的独立判读、交互及图像归属记录见 `38/independent/offline-interactions.json` 和 `38/independent/records-check.json`。

真实公开页覆盖浏览器本地待办的可见结果。键盘提交次数来自运行记录；跨会话传递仅用来让 B 读取 A 产生的同一合成行。异步处理失败、超时、屏外内容与敏感字段遮罩使用受控样本。独立审阅者核对了指定遮罩点在原始及 400% 缩放画面中均为不透明黑色，并抽读既有 T30 历史报告，读取前后摘要相同。像素与历史文件的证据分别见 `38/independent/mask-coordinate.json` 和 `38/independent/historical-read.json`。
