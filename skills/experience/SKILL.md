---
name: experience
description: 按适用范围查询 UI 测试经验的来源、步骤和证据，或从已核验的策略观察登记候选经验。 Use when reviewing evidence-backed scoped strategies, checking prior observations or recording a candidate from a committed step.
---

# 查阅及登记经验

按[经验治理说明](references/experience-governance.md)核对适用空间、项目、产品、系统、模块、功能、检查点、环境和风险。将选中的 ui-test 的 scripts 放在 PYTHONPATH，从 ui_test_core.suite 导入 selected_suite。调用 selected_suite().load_package("experience").query(root, scope)。root 是本次指定的经验目录。missing 列出缺失前置，incomplete 标出缺少依据的记录，records 给出来源运行、步骤、证据和适用范围。交付清单及新增业务尝试数后返回。

查询项目策略时，输入 project、用例步骤 scope、asset 与 build，读取[策略记录](scripts/strategy_learning.py)的来源和适用范围。已有已提交的 V5 策略步骤且获准登记项目候选时，执行 python -m ui_test_core.strategy_learning PROJECT RUN_ROOT STEP。读取返回的候选身份，核对 reuse-experiences/candidates 中的 source、scope 和 strategy。资格复核需要另外的有效运行及来源，不自动进入下一业务阶段。只读查询不改变消费状态。

## Validation

在选定主套件的 scripts 目录运行 python ui_test_suite.py experience --input request.json。输入对象提供root 和 scope，scope 包含治理说明中的八项身份字段。核对 calls、business_attempts_added 和各条来源记录。

## Safety

独立查询只读项目记录。缺少权限或必要前置时交还缺项，保留历史证据。
