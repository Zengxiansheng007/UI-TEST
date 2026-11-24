# CR-20261120-028 · 人工并行与显式串行

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Change Type | changed |
| Scope | core-skill-md, references-and-assets, scripts-and-validation, safety-and-governance |
| Source | UI-TEST #22, #28 |
| Baseline | 18cb00e |
| Author | Codex |
| Related Records | CR-20261120-022 |

## Summary

已隔离 attempt 和会话证据的正式入口，按配置中明确的项目环境或节点集合协调执行。

## Context And Problem

旧收集门拒绝所有 R2 worker，旧 setup 给所有 R2 节点取得项目环境锁。两个独立节点无法并行。

## Sections Changed

pytest 插件、Windows 范围锁、会话汇总及执行指引。

## Decision And Alternatives

复用已有的非阻塞操作系统互斥和 attempt 独占创建；根据配置投影匹配决定，只锁定涉及的范围。

## Detailed Change

范围占用记录为本次未执行。相同会话内重投同节点使用相同运行身份；实际承接时独占创建 attempt，按原有逐例批准与阶段预算执行。

## Impact Analysis

人工独立 CLI、PyCharm 和真实 xdist 共用同一准入入口。2.3 和 2.4 的显式决定采用同一匹配规则。

## Validation Evidence

双 worker 的 load / each 初始回归均命中旧拒绝。修复后包括 2.3 / 2.4 范围争用和阶段预算在内的 56 项验证通过。详见专项验收目录 t28 下的 red.xml 和 green.xml。

独立 CLI 两个进程各自退出 0，真实页面区间重叠 9.694899 秒。双 worker 共享一个会话，退出 0，业务区间重叠 13.702157 秒。两种入口均验证两个节点的原页面断言、逐例 1/2 次提交、截图、trace、RunResultV5 与回执。证据位置为专项验收目录 t28 下 T28-CLI-A、T28-XDIST-A 的 verification.json。

同一 item 重跑与 xdist each 重投均只准入一次。重复投递时单独记录 denied_duplicate_nodes，保留第一次的真实终态与回执，整批保留失败退出码。复核重复、异常、普通单进程及双 worker 的 9 项检查见 duplicate-green.xml。

## Safety And Privacy

写入动作使用原 UI 用例的本轮批准，运行证据留在专项本地目录。

## Risks And Follow-up

真实 IDE 与本次 CLI/xdist 使用不同入口，按 IDE helper 和进程退出证据另行验收。
