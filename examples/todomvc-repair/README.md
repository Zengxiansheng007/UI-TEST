# TodoMVC 两行定位修复

本示例从相邻公开项目复制 TodoPage，在独立目录运行两行源用例。源文件 source_case.py 固定待办文字、原始绑定、勾选状态和剩余数。新增与完成各阶段使用正式 pytest 执行插件、阶段写入预算和 V5 事务。

使用已安装的 Python、pytest-playwright 和 Chromium。UI_TEST_REPAIR_SCRIPTS 指向本仓库 skills/ui-test/scripts 的绝对路径；UI_TEST_CHROMIUM 可指定已有可见浏览器。以下 PROJECT 和 TRIAL 均为此前不存在的独立目录。每次 UI 运行使用新的 ID，只对本次公开练习授权。

1. 在模板目录执行 `python prepare.py initialize PROJECT`。以外来定位器建演练项目时加 `--ownership external`，归属未知时用 `--ownership unknown`。
2. 在 PROJECT 执行 `python -m pytest test_complete.py --ui-run-id OLD19 --ui-r2-approved`。预期在勾选前失败，V5 保留两个新增，目标版本在本用例、步骤、环境及项目范围内暂停。
3. 在模板目录执行 `python prepare.py stage PROJECT --trial TRIAL --failure-run OLD19`。命令读取正式失败结果并反查影响，再将候选版本装入隔离验证副本。
4. 在 TRIAL 执行 `python -m pytest test_complete.py --ui-run-id TRIAL19 --ui-r2-approved`。原用例经过 script.complete、component.ready 和 locator.target，检查两个精确文字对应的勾选状态与计数。
5. 在模板目录执行 `python prepare.py promote PROJECT --trial TRIAL --proof-run TRIAL19`。启用决定引用同版原始失败与回归的 V5 摘要，保留可恢复的 v1 和 v2 实现。
6. 在 PROJECT 执行 `python -m pytest test_complete.py --ui-run-id USE19 --ui-r2-approved`。通过 runs/USE19/finalization/finalization-commit.json 可读回实际 V5 和源步骤使用明细。

每次运行使用独立浏览器上下文。两个新增和一个勾选分别占用独立阶段预算。相同 run ID 不能再次派发写入。页面只放行官方 TodoMVC 自然触发的公开静态资源 GET。
