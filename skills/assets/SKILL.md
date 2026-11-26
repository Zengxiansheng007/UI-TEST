---
name: assets
description: 查询 UI-Test 项目下次运行适用的资产版本、依赖、选版理由和限定范围的启停记录。适用于用例选版及核对存疑发现。 Use for project asset discovery, case-scoped selection, pause decisions and version availability.
---

# 查询当前版本

读取指定项目的 reuse-project.json，明确能力、项目、环境、用例、步骤以及当前授权的 effects 和 facts。checkpoint 为空时显式给 null。查询当时运行所用版本用 run-catalog。

以所选 ui-test 的 scripts 为 PYTHONPATH。用 Python 调用 selected_suite().load_package("assets").query(project, capability, scope, authorization, binding=None)。selected_suite 从 ui_test_core.suite 导入。返回 missing 时只补所列条件。核对 decision.scope、asset.version、tier、dependencies 和 skipped；说明 pauses 限定的版本与范围。pending 含无法确认的项目发现。交付调用清单及新增业务尝试数，结束本次查询。

## 启停

收到限定的项目变更授权时使用本入口的 [AssetCatalog](scripts/asset_revision.py)。发布与暂停均绑定 expected_revision、资产及版本，暂停额外绑定明确 scope。冲突时重新查当前版本和权限。核对项目生效指针及暂停范围，保留历史版本与已运行证据。

## Validation

在选定主套件的 scripts 目录运行 python ui_test_suite.py assets --input request.json。输入对象提供project、capability、scope 和 authorization（含 approved、scope、effects 与 facts）。核对 calls、business_attempts_added 和各条来源记录。

## Safety

独立查询只读项目记录。缺少权限或必要前置时交还缺项，保留历史证据。
