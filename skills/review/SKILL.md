---
name: review
description: Explain why a UI test or a formal Playwright run failed using its assertions and evidence. Use for UI failure attribution including 分析这次 UI 正式运行为什么失败.
---

# UI failure review

仅在明确委托 UI 测试失败归因时使用。普通 Python 代码质量或 PR 评审交给代码评审入口。咨询下一步时由顾问给出建议。

1. 从指定项目的运行登记取回本次的 observations.json 或 RunResult V5。只有用例号时列出匹配运行，由用户选择；多项匹配时停在候选列表。已有准确文件可直接使用。如提供本次证据索引，可从旁边的同名原件核对，或用 --original 指定原件。
2. 将本次选定的主 Skill 的 scripts 加入进程 PYTHONPATH，UI_TEST_SUITE 设为该主 Skill 的目录。从本 Skill 根目录执行 `python scripts/inspect_steps.py <原件或索引>`。V5 的相对证据引用以实际运行目录为根，传入 `--run-root <运行目录>`。将输出 JSON 交还调用方，需持久化时另存为新文件。
3. 根据每个 finding 的原件指针核查当时的断言、页面观察及相应版本。使用 [归因评审标准](references/review-rubric.md) 补充对业务、资产、环境、数据的分析，写出实际依据、待核实项与受影响范围。没有直接证据时保留 unknown；单凭超时或 HTTP 状态不足以认定业务问题。
## Safety

缺少运行、尝试、步骤、原件或对应身份有冲突时说明所需材料。独立调用在交付后结束；跨阶段推进由主入口决定。禁止请求重放、补提交或改写原运行。

## Validation

Run the tests in this Skill's tests directory against the selected installation. Inspect source pointers, attempt identity and any missing-evidence reason in the returned JSON.
