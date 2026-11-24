"""r2_project_lock 和 pytest插件R2锁集成的单元/集成测试。

覆盖：首个获取、第二进程冲突、释放后获取、子进程异常退出恢复、
无显式范围时直接执行、R3拒绝、xdist逐例授权、teardown释放、context manager。
中文注释；不运行测试或输出敏感形状。
"""

import os
import sys
import textwrap
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]  # 启用pytester验证真实插件发现流程。

_SKILL_ROOT = Path(__file__).resolve().parents[1]  # pytester子进程需要显式导入候选Skill。


@pytest.fixture(autouse=True)
def _force_pytester_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONUTF8", "1")  # Windows子进程统一UTF-8输出。
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")


# ---------------------------------------------------------------------------
# 共用配置和conftest模板
# ---------------------------------------------------------------------------

_V21_CONFIG_YAML = textwrap.dedent("""\
    schema_version: "2.3"
    scope:
      project_group: demo
      project_group_name: 示例
      product: demoops-announcement
      product_name: 公告管理
      environment: test
    asset_governance:
      execution_asset_root: "D:\\\\UI-Test"
      knowledge_root: "D:\\\\RAG"
      staging_root: "D:\\\\UI-Test\\\\_tmp"
      forbidden_persistent_roots: ['C:\\']
      layout_version: 1
      levels:
        - project_group
        - product
        - system
        - module_path
        - function
        - case
        - branch
        - run
      segment_naming: stable-id__display-name
      asset_type_policy_version: ui-test.asset-types.v1
    systems:
      - system_id: announcement
        display_name: 公告系统
        modules:
          - module_id: announcement-core
            display_name: 公告核心
            aliases: ["announcement"]
            module_path:
              - module_id: announcement-core
                display_name: 公告核心
            functions:
              - function_id: create-announcement
                display_name: 创建公告
            direct_route_ref: routes/announcement.yaml
    runtime_value_index_ref: "path:D:/UI-Test/_private/runtime-values/demo/demoops-announcement/test/runtime-value-index.yaml"
    runtime_refs:
      base_url: "value:demo-test-base-url"
    checkpoint_runtime:
      root_ref: "checkpoints/announcement.yaml"
    knowledge_space:
      knowledge_space_id: demo-demoops
      relative_path: "demo/demoops-announcement"
    wait_strategy:
      strategy: visible
    semantic_post_signatures: []
    execution_policies: []
    credential_index_ref: "path:D:/UI-Test/_private/runtime-values/demo/demoops-announcement/test/credential-index.yaml"
    pycharm_manual_execution:
      contract_version: 4
      origin_detection: jetbrains-runner-path
      entry_scope: specified-runner
      r2_authorization: auto-test-only
      run_scope: per-node
      r2_parallelism: serial-project-environment
      auto_generate_run_id: true
      auto_approve_r2_visible_ui: true
      finalization_contract: transaction-v1
      run_result_contract: v5
      session_result_contract: v1
      acceptance_contract: external-exit-v1
""")

_PLUGIN_CONTEST = textwrap.dedent(f"""\
    # 根 conftest：显式加载通用 pytest_runtime_plugin
    import sys
    sys.path.insert(0, r"{_SKILL_ROOT}")
    pytest_plugins = ("scripts.ui_test_core.pytest_runtime_plugin",)

    import pathlib

    def pytest_ui_test_project_config_path():
        return str(pathlib.Path(__file__).parent / "ui-test.project.yaml")

    def pytest_ui_test_execution_evidence_root():
        return str(pathlib.Path(__file__).parent / "evidence")

    def pytest_addoption(parser):
        parser.addoption("--ui-pre-submit-only", action="store_true", default=False)
""")


def _write_pycharm_conftest(pytester: pytest.Pytester, config_yaml: str) -> None:
    """写入根conftest（加载插件、提供项目配置路径hook）和项目配置文件。"""
    conftest = _PLUGIN_CONTEST + textwrap.dedent("""\
        import sys
        _runner = pathlib.Path(__file__).parent / "plugins" / "python-ce" / "helpers" / "pycharm" / "_jb_pytest_runner.py"
        _runner.parent.mkdir(parents=True)
        _runner.write_text("# runner\\n", encoding="utf-8")
        sys.argv[0] = str(_runner)
    """)
    pytester.makeconftest(conftest)
    (pytester.path / "ui-test.project.yaml").write_text(config_yaml, encoding="utf-8")


def _write_cli_conftest(pytester: pytest.Pytester, config_yaml: str) -> None:
    """写入CLI来源的conftest（不模拟PyCharm runner路径）。"""
    pytester.makeconftest(_PLUGIN_CONTEST)
    (pytester.path / "ui-test.project.yaml").write_text(config_yaml, encoding="utf-8")


# ===========================================================================
# 单元测试：R2ProjectLock 基础行为
# ===========================================================================

class TestR2ProjectLockUnit:
    # 锁名称派生和基础属性

    def test_lock_name_derived_from_scope(self) -> None:
        # 锁名称仅由project_group/product/environment的SHA-256派生
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock = R2ProjectLock(
            project_group="demo",
            product="demoops-announcement",
            environment="test",
        )
        # 验证锁名称前缀和SHA-256长度
        assert lock.lock_name.startswith("Local\\UIT-R2-")
        assert len(lock.lock_name) == len("Local\\UIT-R2-") + 64

    def test_lock_name_case_insensitive(self) -> None:
        # 大小写不同的scope映射到同一锁名称
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock1 = R2ProjectLock(project_group="Demo", product="DEMOOPS", environment="Test")
        lock2 = R2ProjectLock(project_group="demo", product="demoops", environment="test")
        assert lock1.lock_name == lock2.lock_name

    def test_lock_name_different_scope(self) -> None:
        # 不同scope映射到不同锁名称
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock1 = R2ProjectLock(project_group="demo", product="demoops", environment="test")
        lock2 = R2ProjectLock(project_group="beijing", product="demoops", environment="test")
        assert lock1.lock_name != lock2.lock_name

    def test_lock_name_no_private_values(self) -> None:
        # 锁名称不含原始scope值
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock = R2ProjectLock(
            project_group="super_secret_group",
            product="super_secret_product",
            environment="super_secret_env",
        )
        assert "super_secret_group" not in lock.lock_name
        assert "super_secret_product" not in lock.lock_name
        assert "super_secret_env" not in lock.lock_name

    def test_invalid_scope_raises(self) -> None:
        # 空或非字符串scope必须失败
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock, R2ProjectLockError
        with pytest.raises(R2ProjectLockError):
            R2ProjectLock(project_group="", product="demoops", environment="test")
        with pytest.raises(R2ProjectLockError):
            R2ProjectLock(project_group="demo", product="", environment="test")
        with pytest.raises(R2ProjectLockError):
            R2ProjectLock(project_group="demo", product="demoops", environment="")

    def test_initial_state_not_held(self) -> None:
        # 新创建的锁对象初始状态为未持有
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock = R2ProjectLock(project_group="demo", product="demoops", environment="test")
        assert not lock.is_held


# ===========================================================================
# 单元测试：acquire/release 行为（Windows平台）
# ===========================================================================

class TestAcquireRelease:
    # 首个获取、重复acquire、重复release

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_first_acquire_succeeds(self) -> None:
        # 首个进程获取锁成功
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock = R2ProjectLock(
            project_group="test-pg",
            product="test-prod",
            environment="test",
        )
        try:
            lock.acquire()
            assert lock.is_held
        finally:
            lock.release()

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_double_acquire_raises(self) -> None:
        # 同一锁对象重复acquire报E_R2_PROJECT_LOCK_HELD
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock, R2ProjectLockError
        lock = R2ProjectLock(
            project_group="test-pg2",
            product="test-prod",
            environment="test",
        )
        try:
            lock.acquire()
            with pytest.raises(R2ProjectLockError) as exc_info:
                lock.acquire()
            assert exc_info.value.code == "E_R2_PROJECT_LOCK_HELD"
        finally:
            lock.release()

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_release_allows_reacquire(self) -> None:
        # 释放后可以重新获取
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock = R2ProjectLock(
            project_group="test-pg3",
            product="test-prod",
            environment="test",
        )
        lock.acquire()
        lock.release()
        # 释放后应可重新获取
        lock.acquire()
        assert lock.is_held
        lock.release()

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_double_release_is_safe(self) -> None:
        # 重复release安全拒绝（幂等，不抛异常）
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock = R2ProjectLock(
            project_group="test-pg4",
            product="test-prod",
            environment="test",
        )
        lock.acquire()
        assert lock.release() is True
        assert lock.release() is False  # 重复release明确拒绝，不伪造已释放。
        assert lock.release() is False
        assert not lock.is_held

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_context_manager(self) -> None:
        # context manager正确获取和释放
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock
        lock = R2ProjectLock(
            project_group="test-pg5",
            product="test-prod",
            environment="test",
        )
        with lock:
            assert lock.is_held
        assert not lock.is_held

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_release_failure_is_not_reported_as_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # ReleaseMutex失败必须保留held状态并上报，不能清stash后伪造完成。
        import scripts.ui_test_core.r2_project_lock as lock_module

        class FailingKernel32:
            @staticmethod
            def ReleaseMutex(handle):
                return 0

        lock = lock_module.R2ProjectLock(
            project_group="release-failure-pg",
            product="test-prod",
            environment="test",
        )
        lock._handle = 1
        lock._held = True
        monkeypatch.setattr(lock_module, "_kernel32", FailingKernel32())
        monkeypatch.setattr(lock_module.ctypes, "get_last_error", lambda: 288)

        with pytest.raises(lock_module.R2ProjectLockError) as exc_info:
            lock.release()
        assert exc_info.value.code == "E_R2_LOCK_RELEASE_FAILED:288"
        assert lock.is_held
        lock._held, lock._handle = False, None  # 恢复 Win32 前先注销模拟句柄。

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_second_process_conflict(self) -> None:
        # 子进程持锁并发出READY后，父进程的同scope获取必须立即失败。
        import subprocess
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock, R2ProjectLockError

        child_script = textwrap.dedent(f'''\
            import sys
            sys.path.insert(0, r"{_SKILL_ROOT}")
            from scripts.ui_test_core.r2_project_lock import R2ProjectLock
            lock = R2ProjectLock(project_group="conflict-pg", product="conflict-prod", environment="test")
            lock.acquire()
            print("READY", flush=True)
            sys.stdin.readline()
            lock.release()
        ''')
        child = subprocess.Popen(
            [sys.executable, "-c", child_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        lock2 = R2ProjectLock(project_group="conflict-pg", product="conflict-prod", environment="test")
        try:
            assert child.stdout is not None
            assert child.stdout.readline().strip() == "READY"
            with pytest.raises(R2ProjectLockError) as exc_info:
                lock2.acquire()
            assert exc_info.value.code == "E_R2_PROJECT_LOCK_HELD"
            assert not lock2.is_held
        finally:
            if child.stdin is not None:
                child.stdin.write("release\n")
                child.stdin.flush()
            stdout, stderr = child.communicate(timeout=30)
            assert child.returncode == 0, f"子进程退出失败: {stdout} {stderr}"


# ===========================================================================
# 单元测试：异常进程退出恢复
# ===========================================================================

class TestAbandonedRecovery:
    # 子进程异常退出后锁可恢复

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_abandoned_mutex_recoverable(self) -> None:
        # 子进程获取Mutex后异常退出（不release），父进程应能获取锁
        import subprocess
        from scripts.ui_test_core.r2_project_lock import R2ProjectLock

        # 使用唯一scope避免与其他测试冲突
        pg = "abandon-recovery-test"
        product = "test-prod"
        env = "test"

        # 子进程获取锁后直接退出（不release），模拟异常退出
        child_script = textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, r"{_SKILL_ROOT}")
            from scripts.ui_test_core.r2_project_lock import R2ProjectLock
            lock = R2ProjectLock(
                project_group="{pg}",
                product="{product}",
                environment="{env}",
            )
            lock.acquire()
            # 绕过析构直接结束进程，确保覆盖WAIT_ABANDONED而不是普通release。
            import os
            os._exit(0)
        """)
        result = subprocess.run(
            [sys.executable, "-c", child_script],
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, f"子进程异常退出: {result.stderr}"

        # 父进程应能获取同一scope的锁（WAIT_ABANDONED路径）
        lock = R2ProjectLock(
            project_group=pg,
            product=product,
            environment=env,
        )
        try:
            lock.acquire()
            assert lock.is_held
        finally:
            lock.release()


# ===========================================================================
# 单元测试：工厂函数
# ===========================================================================

class TestCreateFromConfig:

    def test_create_from_valid_config(self) -> None:
        # 从已验证配置创建锁
        from scripts.ui_test_core.r2_project_lock import create_r2_project_lock
        config = {
            "scope": {
                "project_group": "demo",
                "product": "demoops-announcement",
                "environment": "test",
            }
        }
        lock = create_r2_project_lock(config=config)
        assert lock.lock_name.startswith("Local\\UIT-R2-")

    def test_create_from_config_missing_scope(self) -> None:
        # 缺少scope字段报E_R2_LOCK_SCOPE_REQUIRED
        from scripts.ui_test_core.r2_project_lock import create_r2_project_lock, R2ProjectLockError
        with pytest.raises(R2ProjectLockError) as exc_info:
            create_r2_project_lock(config={})
        assert exc_info.value.code == "E_R2_LOCK_SCOPE_REQUIRED"

    def test_create_from_config_invalid_scope(self) -> None:
        # scope字段不完整报E_R2_LOCK_SCOPE_INVALID
        from scripts.ui_test_core.r2_project_lock import create_r2_project_lock, R2ProjectLockError
        with pytest.raises(R2ProjectLockError):
            create_r2_project_lock(config={"scope": {"project_group": "demo"}})


# ===========================================================================
# 单元测试：xdist检测
# ===========================================================================

class TestXdistDetection:

    def test_no_xdist_env(self) -> None:
        # 无xdist环境变量时返回False
        from scripts.ui_test_core.r2_project_lock import detect_xdist_parallel
        assert not detect_xdist_parallel(environ={})

    def test_xdist_worker_env(self) -> None:
        # PYTEST_XDIST_WORKER存在时返回True
        from scripts.ui_test_core.r2_project_lock import detect_xdist_parallel
        assert detect_xdist_parallel(environ={"PYTEST_XDIST_WORKER": "gw0"})

    def test_xdist_worker_count_env(self) -> None:
        # PYTEST_XDIST_WORKER_COUNT存在时返回True
        from scripts.ui_test_core.r2_project_lock import detect_xdist_parallel
        assert detect_xdist_parallel(environ={"PYTEST_XDIST_WORKER_COUNT": "2"})

    def test_xdist_auto_option(self) -> None:
        # --numprocesses=auto不能因int转换失败而被误判为非并行。
        from scripts.ui_test_core.r2_project_lock import detect_xdist_parallel

        class Config:
            def getoption(self, name, default=None):
                return "auto" if name == "--numprocesses" else default

        assert detect_xdist_parallel(config=Config(), environ={})


# ===========================================================================
# 集成测试：pytest插件 R2锁生命周期
# ===========================================================================

class TestDefaultFormalExecution:
    # 无显式范围时，三个风险级别均使用原准入规则。

    def test_r2_qualification_without_serial_constraint(self, pytester: pytest.Pytester) -> None:
        # 模拟 PyCharm 来源以验证候选批准。
        _write_pycharm_conftest(pytester, _V21_CONFIG_YAML)
        pytester.makepyfile(test_r2_lock=textwrap.dedent("""\
            import pytest

            @pytest.mark.ui_test
            @pytest.mark.case_id("CASE-LOCK-001")
            @pytest.mark.branch_id("BRANCH-A")
            @pytest.mark.r2
            def test_r2_lock_acquire(ui_test_execution_context):
                # 确认 setup 产生有效上下文。
                ctx = ui_test_execution_context
                assert ctx.risk_level == "r2-ui-write-test"
        """))
        result = pytester.runpytest_subprocess("test_r2_lock.py", "--ui-pre-submit-only", "-v")
        result.assert_outcomes(passed=1, errors=0, failed=0)

    def test_r0_bypasses_lock(self, pytester: pytest.Pytester) -> None:
        # R0 item不获取锁
        _write_pycharm_conftest(pytester, _V21_CONFIG_YAML)
        pytester.makepyfile(test_r0=textwrap.dedent("""\
            import pytest

            @pytest.mark.ui_test
            @pytest.mark.case_id("CASE-R0-001")
            @pytest.mark.branch_id("BRANCH-A")
            @pytest.mark.r0
            def test_r0_no_lock(ui_test_execution_context):
                # R0不获取锁，正常通过
                assert ui_test_execution_context.risk_level == "r0-read-only"
        """))
        result = pytester.runpytest_subprocess("test_r0.py", "-v")
        result.assert_outcomes(passed=1)

    def test_r1_bypasses_lock(self, pytester: pytest.Pytester) -> None:
        # R1 item不获取锁
        _write_pycharm_conftest(pytester, _V21_CONFIG_YAML)
        pytester.makepyfile(test_r1=textwrap.dedent("""\
            import pytest

            @pytest.mark.ui_test
            @pytest.mark.case_id("CASE-R1-001")
            @pytest.mark.branch_id("BRANCH-A")
            @pytest.mark.r1
            def test_r1_no_lock(ui_test_execution_context):
                assert ui_test_execution_context.risk_level == "r1-read-only-authenticated"
        """))
        result = pytester.runpytest_subprocess("test_r1.py", "-v")
        result.assert_outcomes(passed=1)


class TestPluginR3Blocked:
    # R3 item在BrowserContext前报E_R3_BLOCKED

    def test_r3_blocked(self, pytester: pytest.Pytester) -> None:
        _write_pycharm_conftest(pytester, _V21_CONFIG_YAML)
        pytester.makepyfile(test_r3=textwrap.dedent("""\
            import pytest

            @pytest.mark.ui_test
            @pytest.mark.case_id("CASE-R3-001")
            @pytest.mark.branch_id("BRANCH-A")
            @pytest.mark.r3
            def test_r3_blocked(ui_test_execution_context):
                pass
        """))
        result = pytester.runpytest_subprocess("test_r3.py", "-v")
        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(["*E_R3_BLOCKED*"])


@pytest.mark.parametrize("distribution", ["load", "each"])
def test_xdist_runs_each_approved_r2_instance_once(pytester, distribution):
    pytest.importorskip("xdist")
    _write_cli_conftest(pytester, _V21_CONFIG_YAML)
    pytester.makepyfile(test_writes="""
        import pytest
        from pathlib import Path

        @pytest.mark.parametrize("value", [1, 2])
        @pytest.mark.ui_test
        @pytest.mark.case_id("CASE-XDIST")
        @pytest.mark.branch_id("BRANCH-A")
        @pytest.mark.r2
        def test_node(value, ui_test_execution_context):
            assert ui_test_execution_context.approved
            with Path(f"calls-{value}").open("a") as stream:
                print("one dispatch", file=stream)
    """)
    result = pytester.runpytest_subprocess("test_writes.py", "-n", "2", "--dist", distribution,
                                           "--ui-r2-approved", "--ui-pre-submit-only")
    for value in (1, 2):
        assert (pytester.path / f"calls-{value}").read_text().splitlines() == ["one dispatch"]
    if distribution == "each":
        result.assert_outcomes(passed=2, errors=2)
        import json
        summary, = (pytester.path / "evidence/sessions").glob("*.json")
        session = json.loads(summary.read_text(encoding="utf-8"))
        assert session["session_status"] == "failed" and session["pytest_exitstatus"] == result.ret
        assert set(session["denied_duplicate_nodes"]) == set(session["expected_nodes"])
        assert all(row["disposition"] == "passed" and row["terminal_ref"] for row in session["nodes"])
    else:
        result.assert_outcomes(passed=2)


@pytest.mark.parametrize("version", ["2.3", "2.4"])
def test_explicit_scope_conflict_prevents_fixture_and_preserves_neighbor(pytester, version):
    import json
    import yaml
    from scripts.ui_test_core.r2_project_lock import create_r2_project_lock

    blocked = "test_scope.py::test_business[blocked]"
    neighbor = "test_scope.py::test_business[neighbor]"
    decision = dict(scope="nodes", node_ids=[blocked], decision_ref="approval:shared-object")
    config = yaml.safe_load(_V21_CONFIG_YAML)
    if version == "2.3":
        (pytester.path / "ui-test.serial-constraints.json").write_text(json.dumps([decision]))
    else:
        config.update(schema_version="2.4", serial_constraints=[decision])
        policy = config["pycharm_manual_execution"]
        policy.update(contract_version=5, session_result_contract="v2")
        del policy["r2_parallelism"]
    _write_cli_conftest(pytester, yaml.safe_dump(config))
    pytester.makepyfile(test_scope="""
        import pytest
        from pathlib import Path
        @pytest.mark.parametrize("value", ["blocked", "neighbor"])
        @pytest.mark.ui_test
        @pytest.mark.case_id("CASE-SCOPE")
        @pytest.mark.branch_id("primary")
        @pytest.mark.r2
        def test_business(value, ui_test_execution_context):
            assert ui_test_execution_context.approved
            Path(value).touch(exist_ok=False)
    """)
    with create_r2_project_lock(config=config, node_ids=(blocked,)):
        result = pytester.runpytest_subprocess("test_scope.py", "--ui-pre-submit-only", "--ui-r2-approved")
    result.assert_outcomes(passed=1, errors=1)
    assert "该范围被占用，本次未执行" in result.stdout.str()
    assert not (pytester.path / "blocked").exists() and (pytester.path / "neighbor").exists()
    summary, = (pytester.path / "evidence/sessions").glob("*.json")
    entries = {row["node_id"]: row for row in json.loads(summary.read_text(encoding="utf-8"))["nodes"]}
    assert entries[blocked]["disposition"] == "not_executed"
    assert blocked in entries[blocked]["missing_reason"] and "attempt_ref" not in entries[blocked]
    assert entries[neighbor]["disposition"] == "passed"


def test_automatic_id_redelivery_cannot_reopen_completed_attempt(pytester):
    _write_pycharm_conftest(pytester, _V21_CONFIG_YAML)
    with (pytester.path / "conftest.py").open("a", encoding="utf-8") as conftest:
        conftest.write(textwrap.dedent("""
            import pytest

            @pytest.hookimpl(tryfirst=True)
            def pytest_runtestloop(session):
                item, = session.items
                for _ in range(2):
                    item.ihook.pytest_runtest_protocol(item=item, nextitem=None)
                return True
        """))
    pytester.makepyfile(test_replay="""
        import pytest
        from pathlib import Path
        @pytest.mark.ui_test
        @pytest.mark.case_id("CASE-RERUN")
        @pytest.mark.branch_id("primary")
        @pytest.mark.r2
        def test_once(ui_test_execution_context):
            with Path("admissions").open("a") as stream:
                print(ui_test_execution_context.run_id, file=stream)
    """)
    result = pytester.runpytest_subprocess("test_replay.py", "--ui-pre-submit-only")
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*E_ATTEMPT_START_ALREADY_EXISTS*"])
    assert len((pytester.path / "admissions").read_text().splitlines()) == 1
    terminal, = (pytester.path / "evidence/attempts").glob("*/terminal.json")
    import json
    assert json.loads(terminal.read_text())["status"] == "passed"


@pytest.mark.parametrize("environment,approval,expected", [
    ("test", [], "E_UI_TEST_R2_APPROVAL_REQUIRED"),
    ("staging", ["--ui-r2-approved"], "E_UI_TEST_R2_TEST_ENVIRONMENT_REQUIRED"),
])
def test_worker_requires_own_test_environment_and_approval(pytester, environment, approval, expected):
    pytest.importorskip("xdist")
    project = _V21_CONFIG_YAML.replace("environment: test", f"environment: {environment}")
    project = project.replace("/test/", f"/{environment}/")
    _write_cli_conftest(pytester, project)
    pytester.makepyfile(test_worker="""
        import pytest
        from pathlib import Path
        @pytest.mark.ui_test
        @pytest.mark.case_id("CASE-WORKER")
        @pytest.mark.branch_id("primary")
        @pytest.mark.r2
        def test_run(ui_test_execution_context):
            Path("fixture-reached").touch()
    """)
    result = pytester.runpytest_subprocess("test_worker.py", "-n", "2", "--ui-run-id", "R2-GUARD", *approval)
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*" + expected + "*"])
    assert not (pytester.path / "fixture-reached").exists()
    assert not list((pytester.path / "evidence/attempts").glob("*/attempt-start.json"))


class TestPluginTeardownRelease:
    # teardown正确释放锁

    @pytest.mark.skipif(
        sys.platform != "win32" and os.name != "nt",
        reason="Windows命名Mutex测试需要Windows平台",
    )
    def test_lock_released_after_test(self, pytester: pytest.Pytester) -> None:
        # R2测试完成后锁应释放；第二个测试可获取
        _write_pycharm_conftest(pytester, _V21_CONFIG_YAML)
        pytester.makepyfile(test_release=textwrap.dedent("""\
            import pytest

            @pytest.mark.ui_test
            @pytest.mark.case_id("CASE-REL-001")
            @pytest.mark.branch_id("BRANCH-A")
            @pytest.mark.r2
            def test_release_first(ui_test_execution_context):
                pass

            @pytest.mark.ui_test
            @pytest.mark.case_id("CASE-REL-002")
            @pytest.mark.branch_id("BRANCH-A")
            @pytest.mark.r2
            def test_release_second(ui_test_execution_context):
                pass
        """))
        result = pytester.runpytest_subprocess("test_release.py", "--ui-pre-submit-only", "-v")
        # 两个R2测试都应通过：第一个释放后第二个可获取
        result.assert_outcomes(passed=2)
