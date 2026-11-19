# 连续用例阶段预算扩展

版本：stage-budget-v1。仅用于项目契约2.2的显式stage_write_policies，按case_id和branch_id精确匹配，环境必须为test。未配置的用例保留默认单次写入行为。

- 每个完整用例仍只创建一个隔离BrowserContext；阶段不是新用例，保存后不关闭会话。
- 策略不授予R2权限；仍需当前run授权、稳定runner、active identity、输入hash门禁和跨进程串行锁。
- 阶段ID有序且唯一，每阶段一次；许可不能重复发放/消费，前一阶段未知或失败时不能推进。
- stage_write_budget及budget_hash进入ExecutionContextV3.config_summary、运行快照、R2ApprovalRecordV2和RunResultV5。没有该显式扩展时，approval最大次数和RunResult提交次数仍不得超过1。
- RunResultV5.phase_results逐阶段记录实际次数与结果；submit_count必须等于各阶段之和。只有全部阶段verified且pytest各阶段通过才可passed。
- 多阶段初始资格仅证明first-write-boundary，明确列出deferred_phase_ids。不得把第一处保存前的检查当成整个用例验证。
- 运行中每个后续保存前，仍在同一上下文验证当前阶段完整前置、hash和截图，记录phase-boundary资格，再消费一次许可。
- 显式阶段预算用例即使pytest失败，也尝试提交真实的失败RunResult与证据；terminal仍为failed，不能升级为passed。旧失败结果不回填改写。
- 旧V1/V2等历史聚合器与默认单写入规则不变，禁止把新阶段结果降级转换后宣称通过。
