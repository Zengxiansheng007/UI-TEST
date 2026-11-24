# 编写前的共享状态核对

探索结束后，结合当前探索包已有的可见状态、用例步骤及断言核对同一业务对象。HTTP 证据仅引用获准 UI 操作自然产生的流量。禁止主动请求、查询或重放接口来补证。使用已脱敏的引用。

## 探索交给验证

如果 A 的写入能改变 B 要读取的业务状态，随脚本交付一条具体冲突。记录写方与读方用例、共享对象、各自动作、受影响的断言及原因、现有证据引用。编写前可用 Source Case 和步骤引用，准备并发时解析为实际参数化 nodeid。不同会话也可能指向同一个服务端对象。缺少对象相同的证据时记录已知条件，照常编写。不要仅凭同页、同控件或名称相同就要求接受冲突。

## 主任务准备执行

1. 只要求编写，或要求“尽快跑完”时，照常编写；执行按默认串行，依次等待收尾。已有具体冲突随脚本说明，无须为此询问。
2. 用户明确要求并发时，核对项目显式限制与本任务实际选定的节点。仅对其中两端均入选且未明确接受的冲突，说明具体断言如何失真并询问。等待涉及的节点，已获并发授权的其余独立节点可继续。未获授权的节点不可加入。
3. 原指令已经点明并接受该冲突时，直接使用该消息引用。后续处理同一批次，从已有决定核对任务、批次、完整节点集合，以及写方、读方、对象、读写动作和断言。相同范围和冲突复用原引用；改变任一项则重新判断。用例新增佐证、节点枚举顺序变化均不单独触发重问。仍按原断言核对实际结果。
4. 将冲突与明确接受它的 instruction_ref 一起交给调度者。子代理回传节点及决定。主任务统一派发。项目串行设置及现有 R2 写入批准、预算、未知结果停止规则仍然生效。

## 交接字段

`scope` 包含 task_ref、batch_ref、nodes（已展开的完整授权集合）。`conflict` 包含 writer、reader、object_ref、write_action、read_action、assertion、evidence_refs。`Acceptance(scope, conflict, instruction_ref)` 引用明确接受该风险的用户消息；只要求并发的消息不能当作该决定。主包的 `ui_test_core.shared_state_conflict.accepted_instruction` 核对结构，返回匹配决定的消息引用；调用者核对引用所指消息与具体风险。

可按[共享待办练习](../assets/examples/shared-todo-conflict.md)演练上述决定。

## 启动获准的并行批次

从项目目录使用现有主任务的绝对状态文件路径。例中用户明确要求并发运行两个参数化节点。将实际消息引用和确认为本批范围的完整 nodeid 写入 UTF-8 JSON。文件选择会重新收集和核对，集合有差异时在 UI 操作前停止。

~~~json
{
  "task_ref": "D:/work/task.json",
  "batch_ref": "ab",
  "instruction_ref": "user-message/explicit-ab",
  "nodes": ["test_todo.py::test_count[active]", "test_todo.py::test_count[completed]"],
  "conflicts": [],
  "method": "auto"
}
~~~

~~~text
python <ui-test>/scripts/codex_dispatch.py --task-ref D:/work/task.json --batch-ref ab --node test_todo.py --parallel-intent intent.json
~~~

方法 `auto` 优先采用当前 pytest 已加载的 xdist，否则同时启动独立进程。指定 `xdist` 或提供 `-- -n 2 --dist=load` 时，缺少插件会报告 `E_CODEX_XDIST_UNAVAILABLE`。指定 `independent` 使用独立会话。并发运行 R2 时，逐例核对用户批准、目标、环境及阶段预算后，在 pytest 参数中另传 `--ui-r2-approved`。

将已知共享状态风险逐条填入 `conflicts`。已有明确风险决定时，添加 `acceptances` 数组，每条含上文所列的 `scope`、`conflict` 和 `instruction_ref`。未决定的风险仅暂停该风险两端，日志列出对象、读写、断言和证据。补入决定后用同一批次重入。项目串行范围中的节点分次派发。任务 JSON 保留已接受决定、实际启动的节点与 PID、各组退出及逐例会话引用。遇到退出或终态未知，保留本次记录和其他节点的结论。
