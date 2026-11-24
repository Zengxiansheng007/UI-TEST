# CR-20261120-022 · 正式 Playwright 执行

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Change Type | changed |
| Scope | references-and-assets, scripts-and-validation, safety-and-governance, downstream-and-handoff |
| Source | UI-TEST #22, #23, #24 |
| Baseline | 6353a98 |
| Author | Codex |
| Related Records | CR-20261120-026 |

## Summary

正式插件读取有效并发策略，将每次执行与相应运行目录及回执关联。

## Context And Problem

旧模板将所有 R2 执行视为需要项目互斥。其他进程收集节点时可能写入活动运行的恢复记录。

## Sections Changed

涉及项目配置、上下文与会话 Schema、执行插件、attempt 存储和恢复器，以及 TodoMVC 正式归档。

## Decision And Alternatives

保留旧版本读取规则，将新决策写入新版本记录。定向恢复只使用执行进程绑定的目标。

## Detailed Change

配置 2.3 先经原 Schema 校验，再将历史模板默认值与单独记录的用户决定区分。2.4 直接声明约束。新执行写 ExecutionContextV5 和 SessionResultV2。读取器保留对原 V4/V1 和逐例 RunResultV5 的支持。

## Impact Analysis

收集曾触发共享恢复扫描。现在执行进程在浏览器启动前取得 attempt 所有权，将正式证据归档到本次运行。恢复器核对同一把锁、该进程绑定的目录、已有终态与回执。无法确定归属时维持只读。

## Validation Evidence

| 修改 | 验证及证据 |
| --- | --- |
| #23，234f1c7 | 同一公开用例按配置 2.3 / 2.4 分别运行，两个 session 均退出 0，分别产生五步截图及两次获准阶段提交。运行标识 ISSUE23-LEGACY-01、ISSUE23-CURRENT-01。 |
| #24，20ddc8c、2e95449 | 同一正式节点的两次独立运行分别归档 35 个文件，第二次运行和 worker 替换后复算摘要一致。准确提交的四项检查覆盖未知所有者、活动所有者和两个硬退出边界。 |

## 批次运行及集成回归

#25 的 controller 汇总按实际节点核对终态、回执与 pytest 退出，报告修订见报告包 CR-20261120-025。#27 的任务启动器在上一子进程退出且正式回执可复核后派发下一节点。公开 TodoMVC 两例的进程间隔为 2.573 秒。#28 的独立 CLI 与双 worker 会话分别获得 9.695 秒、13.702 秒业务区间重叠，手动入口修改见本包 CR-20261120-028。真实 IDE 验收仍需其自身的运行回执。

主包集成回归首轮 518 项通过，2 项跳过，2 项失败。按正式包入口重算当前文件清单和 SKILL.md 摘要，修复注册表检查。长路径扫描测试改用短临时根复核，两组定向复核合计 15 项通过。

## Safety And Privacy

原始截图与含本机路径的证据保存在专项验收目录。所有浏览器业务取证均使用授权 UI 操作。

## Risks And Follow-up

批次调度和真实 IDE、CLI、xdist 验收由其余工单交付。
