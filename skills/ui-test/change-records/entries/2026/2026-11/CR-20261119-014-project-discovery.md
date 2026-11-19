# CR-20261119-014 · 项目文件发现与恢复

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | ui-test |
| Issue | #14 |

## Summary

从项目声明和配置目录恢复资产查询。

## Context And Problem

旧入口只识别一项导航。

## Sections Changed

scripts-and-validation，examples/todomvc。

## Decision And Alternatives

静态读取 Python AST 和文件摘要。所有目录及恢复文件必须在项目内。

## Detailed Change

discover 返回版本、位置、依赖、适用范围和缺失原因。applicable 根据依赖和暂停范围判定可用性。dependents 反查依赖，trace_run 通过本次正式结果回读证据。

## Impact Analysis

正常源用例 OPEN 在调用前查询当前环境。已有绑定及其原始断言继续运行。

## Safety And Privacy

扫描过程只解析文件。练习站按原有 UI 预算运行。

## Risks And Follow-up

当前声明格式支持 Python 类、方法和直接 self 属性赋值。其它结构需要核对。

评审修复后的 `REUSE14-20261119-003` 用空 pycache 路径从正常节点执行到首次提交前，1 passed。回读 qualification/navigation-use.json 确认 v1 真实进入、列表为空且断言通过，qualification-0.json 记录 prior_submit_count=0。隔离项目的其他新进程仅凭正式声明恢复 locator.rows 的目标用例暂停，拦截 script.complete。修复后的 `--require-change-records` 返回 validated-candidate，P0/P1/P2 均为零。

## Validation Evidence

正式回归 `skills/ui-test/tests/test_project_asset_discovery.py` 四项通过。覆盖跨目录移动、同内容副本歧义、同名外部修改、独立声明发现及冲突、传递依赖、暂停和缺失版本。独立评审发现未声明脚本缺少登记、外改内容缺少恢复副本，新增反例先失败后通过。未声明及外改文件使用独立候选身份，保留 AST 符号、来源、原因和字节；源文件移除后仍能从项目 `.reuse-candidates` 回读，候选无法执行。先前的两项目录样本及红测保存在 `.scratch/reuse14`。

运行 `REUSE14-20261119-002` 由公开项目正常 pytest 节点执行，退出码 0，1 passed，生成器原有 p0 标记警告一条。新 Python 进程在独立空 pycache 路径下使用正式文件回读提交的 V5，确认 `flow.open-todomvc` v1、摘要 `804d6ef1132ce54b4548521670034e1c84c26f91a0c6ad1a9bd48f7a8233b555`、尝试 `attempts/881458c994ede302-3c15f56f989be084`、真实入口、导航断言及空列表。源用例的新增、勾选与剩余计数断言通过。反查 `locator.rows` 命中 `component.ready` 与 `script.complete`。从 `examples/todomvc/asset-paths.json` 的 TODO-P0-002 branch_root 可定位 runs 下同号运行。

