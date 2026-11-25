# CR-20261125-050 · Windows 定时生成待审清单

| Field | Value |
|---|---|
| Status | applied |
| Target Skill | ui-test |
| Baseline | 2e01e94 |
| Scope | scripts-and-validation, core-skill-md |
| Requirement | #50 · P2-R02 · AC-01、AC-02 |

## Summary

项目可注册固定本地程序的 Windows 普通用户任务。按 30 天和登录触发检查到期周期；验收模式仅注册一次定时触发。

## Context And Problem

错过周期的项目需要在登录时补做，两个相邻入口须避免重复成功清单。

## Sections Changed

项目治理入口、定时任务配置、到期判断及使用说明。

## Decision And Alternatives

周期从首次启用的本地时间起算，到期后以日期构造项目内幂等请求。清单由既有预演程序封存。

## Impact Analysis

每项目和用户拥有独立计划任务，动作绑定本地 Python、治理入口和项目位置。运行期间无归档、释放或业务页面操作。

## Validation Evidence

单测覆盖首次到期、跨周期、失败重试和重叠触发。Windows 实机验收对读系统执行记录和项目新清单。

## Safety And Privacy

使用 InteractiveToken 和 LeastPrivilege，无账户口令。验收专用一次触发与周期配置分开。

## Risks And Follow-up

已绑定的 Python 和 Skill 安装位置需可读；登录补跑依赖当前用户启动会话。
