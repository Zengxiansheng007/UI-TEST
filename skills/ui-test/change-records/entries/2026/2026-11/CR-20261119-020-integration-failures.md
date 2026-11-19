# CR-20261119-020 · #12 集成修复的逐步暂停及环境证据

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Change Type | fixed |
| Scope | scripts-and-validation |
| Source | #12 集成独立评审 |
| Baseline | 主例 project_runtime.py SHA-256 前缀 1f4091192c6a，修复例 test_complete.py 前缀 5c18613659e6 |
| Related Records | CR-20261119-017、CR-20261119-018、CR-20261119-019 |

## Summary

正常 pytest 入口现可在真实导航后辨认过期态，在就绪组件和完成脚本入口错误时暂停准确版本，在两行用例勾选前消费最新暂停决定。

## Context And Problem

主例已有步骤通过时，异常处理丢失失败资产身份；初始空页面也无法呈现目标站的过期态。两行示例在勾选前只检查定位器，运行中对脚本和组件的暂停未得到执行。

## Sections Changed

通用 reusable_assets.py 增加固定版本与传递依赖的暂停检查。两个示例在调用与写预算边界使用同一检查。主例在加载器发现入口契约不符时携带失败资产的身份和执行范围。

## Decision And Alternatives

就绪组件可按当前可证实的前提提前完成选择，执行时再查暂停。没有资格时留到就绪步骤重新选择。导航调用和后续组件各自保留其真实进入状态。

## Detailed Change

导航后的页面显示过期文本时归类为环境失败。已选且未及执行的后续组件保留步骤回执。加载器将准确版本绑定到失败步骤。两行示例在加载定位器、脚本与就绪组件前，以及就绪调用后扣减勾选预算前，核对固定版本在本范围的暂停决定。

## Impact Analysis

改动面为两个练习项目和一个共用的只读暂停查询。在全新项目副本按源用例执行旧版失败、候选回归和启用后的再次复用。本轮保留以往原始回执与示例版本。

## Validation Evidence

主例根目录为 [local artifact]，各模式的 branch/runs/<运行>/finalization/finalization-commit.json 指向 V5。两行例根目录为 [local artifact]，各项目的 runs/<运行>/finalization/finalization-commit.json 指向 V5。表中摘要为各次 V5 的 SHA-256 前缀。

| 运行 | 副本 | 核实结果 | 摘要 |
| --- | --- | --- | --- |
| MAIN12REXPIRED | expired | 导航进入、后续就绪组件已选未进入、环境原因、零写、零暂停 | d00528ac9b70 |
| MAIN12RREADY | ready | 新增一次后在 READY-COMPLETE 只暂停 component.ready v1 | 8a589e2e84a4 |
| MAIN12RCOMPLETE | complete | 新增一次后在 COMPLETE 只暂停 script.complete v1 | 11baf0dd8ac2 |
| OLD12R | project | 旧定位器命中两行，保持两次新增与零勾选 | 4632246110e8 |
| TRIAL12R | trial | 原断言通过，目标独自勾选，剩余数 2→1 | 368b1e7a74e3 |
| USE12R | project | 启用后在新上下文再次通过原断言 | 211f6ca0d373 |
| PAUSE12R0 | pause0 | 就绪读取后暂停脚本，两次新增，零勾选 | 14272d9de80b |
| PAUSE12R1 | pause1 | 就绪读取后暂停就绪组件，两次新增，零勾选 | 27d1797c1232 |
| PAUSE12R2 | pause2 | 就绪读取后暂停传递定位器，两次新增，零勾选 | 75359a551c24 |

运行脚本 .scratch/reuse20/integration_fix/run_review.py 独立启动正式 pytest 子进程，读取提交后的 V5 检查业务状态、资产范围及预算。test_asset_repair.py 与 test_reuse_failure.py 合计 7 项通过。

create-skill 的 --require-change-records 校验结果为 validated-candidate，P0/P1/P2 均为 0。报告保存在 .scratch/reuse20/integration_fix/change-record-validation.json。本轮变更文件的常见密钥与私钥标记扫描无命中。

## Safety And Privacy

测试只使用公开 TodoMVC 练习及隔离文件，截图和动作范围均限于练习数据。保留基于静态 GET 白名单的请求观察。

## Risks And Follow-up

会话过期使用浏览器真实导航时返回的本地过期页面响应。公开站没有账号会话，本结果覆盖该页态的分类、跳过和零写行为。
