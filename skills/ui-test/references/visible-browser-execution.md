# 可见浏览器与运行额度

## 适用范围
在 Midscene 探索、Playwright 编写验证、提交前 qualification 和正式 UI 回归前读取。
实际浏览器必须显示在工程师可观测的桌面会话中；截图、trace、HTML 报告不能代替窗口。
纯静态编写、测试收集和离线单元测试无需启动浏览器。

## 启动与观测
Python Playwright 使用 browser_type.launch(headless=False)；
Midscene 的 JavaScript Playwright 载体使用 chromium.launch({ headless: false })。
连接已有浏览器时核对真实窗口可见，不另建隐藏会话。

pytest-playwright 必须核对根 conftest、共享 fixture 和生成模板，避免覆盖 --headed：

    @pytest.fixture(scope="session")
    def browser_type_launch_args(browser_type_launch_args):
        return {**browser_type_launch_args, "headless": False}  # 显示窗口，保留其余参数。

运行前检查最终启动参数，运行后用真实窗口或操作系统窗口证据确认已显示。
没有桌面会话时停止并报告原因，不自动切换 headless。
仅用户明确要求无头运行时可例外，记录授权来源及实际参数。
不强制固定等待、额外慢速、调试暂停或永不关闭窗口；工程师要求后再配置。
结束时正常释放浏览器资源，按原规范保留截图及失败证据。

## 当前运行与历史批次额度
窗口可见不授予 R2，也不授权向模型发送私有页面。
当前节点授权仍由通用 pytest 插件和项目策略生成，runtime 仅消费验证后的上下文。
一次性 Agent 批次的“每用例一次”额度与工程师独立 Run/Rerun/Debug 的当前 run 额度必须隔离。
不得用历史 case_id 永久占用记录全局阻断具备独立授权的新 PyCharm run。
不得删除旧记录、复用旧批准、仅凭来源名称授予写权限，或让 CLI/Codex 绕过已耗尽额度。
同一 run 的第二次提交始终失败；qualification 始终零提交，历史失败保持原状。

## 验证与影响范围
修改现有 fixture 时同步参与构建身份的模板，重新编译，完成匹配版本的零提交 qualification 后激活。
禁止修改不可变历史 manifest 来伪造 in_sync。
验证覆盖窗口可见、已批准新 run、同 run 重复提交、未批准/来源不匹配/非测试环境、
历史批次额度耗尽以及 qualification 不提交。
