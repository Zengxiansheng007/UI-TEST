# #26 编写前共享状态风险核对

范围为 #22 的 AC4 编写与决定复用部分。基线为 6353a98。三个技能的变更记录分别为主包 CR-20261120-026、探索 CR-20261120-027、验证 CR-20261120-028。

## 本地前向演练

输入为合成待办系统的探索观察。A 通过 UI 完成团队待办 42；B 在同一团队清单核对 42 为“待处理”；C 读取帮助标题。证据引用见[场景](../../skills/ui-test/assets/examples/shared-todo-conflict.md)，字段定义见[共享状态核对](../../skills/ui-test/references/shared-state-conflicts.md)。本轮由编写者按三个 Skill 入口桌面推演，未调用外部模型或运行浏览器。

| 提供给作者或主任务的指令 | 从技能得到的处置 |
|---|---|
| “根据这份探索结果把 A、B 写好，尽快跑完。” | 探索交出两端步骤和证据；验证指出 A 先完成后 B 的待处理断言会失败。继续编写，执行默认串行。 |
| “并发跑 A、B、C。” | 明确询问是否接受 42 的状态改变影响 B；等待 A/B，允许独立 C 继续。 |
| “我接受这次 A 完成 42 后 B 状态断言失败，继续并发。”稍后同一任务接续同一批。 | 使用该冲突的明确消息引用，恢复同一范围无需再次询问。原断言仍执行。 |
| “把 B 换成另一条参数化节点”，或原对象换为 43，或断言改为“行存在”。 | 核对新证据和新冲突。已有接受消息不覆盖变化的节点、对象或断言。 |
| “把两个各自本地存储的待办用例写好。” | 看到状态隔离证据后直接编写。 |

## 可重复检查

- `PYTHONPATH=skills/ui-test/scripts`，使用现有 Python 3.11 执行 `-m pytest -q skills/ui-test/tests/test_shared_state_conflict.py`。基线红灯为缺少 shared_state_conflict 模块。实现后 11 项通过。
- 对三个包分别执行 create-skill 的 `scripts/validate_create_skill.py <包目录> --require-change-records`。三包均为 validated-candidate，P0/P1/P2 均为零。
- 样例和测试仅使用合成对象及引用；未安装或部署技能。运行入口、项目强制串行、真实 PyCharm/xdist、V5 业务证据仍由对应交付验证。

## 集成回归修复

在 5689e95 单跑 `test_generic_active_surfaces_have_no_project_specific_identifiers` 可复现失败。主入口和通用参考包含项目标识检查禁止的文字，通用参考还内嵌了合成项目对象。将完整的演练及数据移入主包 assets/examples，主入口和通用参考链接到该场景。保持原扫描范围和断言。

执行 `-m pytest -q skills/ui-test/tests/test_v2_schema_registry.py::test_generic_active_surfaces_have_no_project_specific_identifiers skills/ui-test/tests/test_shared_state_conflict.py`，12 项通过。主包重跑 `--require-change-records` 得到 validated-candidate，P0/P1/P2 均为零。
