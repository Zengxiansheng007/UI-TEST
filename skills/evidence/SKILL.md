---
name: evidence
description: Use when organizing UI test step evidence from Midscene observations or RunResult V5, linking the attempt, screenshots, matched page responses and missing evidence.
---

# UI step evidence

整理已有步骤证据或处理 Packet 3.0 的 collect-evidence 时使用此入口。保留原有 run、case、branch、attempt 和 step 身份。

1. 从指定项目的运行登记取回本次的 observations.json 或 RunResult V5。只有用例号时列出匹配运行，由用户选择；多项匹配时停在候选列表。已有准确文件可直接使用。
2. 将本次选定的主 Skill 的 scripts 加入进程 PYTHONPATH，UI_TEST_SUITE 设为该主 Skill 的目录。从本 Skill 根目录执行 `python scripts/inspect_steps.py <原件>`。V5 的相对证据引用以实际运行目录为根，传入 `--run-root <运行目录>`。将输出 JSON 交还调用方，需持久化时另存为新文件。
3. 每行含身份、原件 JSON Pointer、图片位置或缺项、经同会话匹配的监听摘要。按 [证据分层](references/evidence-taxonomy.md) 查阅原件；截图引用相对运行目录。不回显请求头、响应正文、测试值。
## Safety

缺少运行、尝试、步骤、原件或对应身份有冲突时说明所需材料。独立调用在交付后结束；跨阶段推进由主入口决定。禁止请求重放、补提交或改写原运行。

## Validation

Run the tests in this Skill's tests directory against the selected installation. Inspect source pointers, attempt identity and any missing-evidence reason in the returned JSON.
