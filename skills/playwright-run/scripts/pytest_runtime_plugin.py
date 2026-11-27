"""通用 pytest 执行上下文插件：注册参数、分类来源、绑定 node、生成 ExecutionContextV2。

本插件是执行上下文的唯一控制层。项目 runtime 通过 ``ui_test_execution_context`` fixture
消费已验证上下文，不得自行识别 PyCharm 来源、生成 Run ID 或授予 R2 批准。
匹配项目显式串行范围的节点在 fixture 前取得范围锁。
记录setup/call/teardown阶段事件并在正常pytest生命周期末生成唯一terminal。
新增execution evidence root hookspec。
"""

from __future__ import annotations

import hashlib  # 生成不暴露本机路径的来源与配置摘要。
import json  # 读取ExecutionContextV2 Schema。
import os
import re  # 校验Run ID和摘要格式。
import uuid  # 为每个pytest宿主进程生成唯一session identity。
from dataclasses import asdict, dataclass  # 构建并验证只读上下文对象。
from datetime import UTC, datetime  # 生成SessionResult时间戳。
from pathlib import Path  # 读取项目配置文件。
from typing import Any, Callable, Mapping  # 声明稳定的输入结构。

import pytest  # pytest 插件入口与 hookspec 依赖。
from jsonschema import Draft202012Validator  # 在上下文进入fixture前执行正式Schema校验。

from contextlib import ExitStack
from ui_test_core.case_contracts import canonical_hash, validate_document
from ui_test_core.execution_attempt_store import (
    ExecutionAttemptStore,
    ExecutionAttemptStoreError,
    derive_attempt_directory_name,
)
from ui_test_core.pycharm_runtime import classify_execution_origin, resolve_pycharm_run_context
from ui_test_core.session_evidence import FormalSession
from ui_test_core.finalization_transaction import FinalizationTransaction, FinalizationTransactionError
from ui_test_core.project_config import ProjectConfigError, load_project_config
from ui_test_core.path_utils import io_path
from ui_test_core.r2_project_lock import (
    R2ProjectLockError,
    create_r2_project_lock,
)


from ui_test_core.suite import selected_suite

SKILL_ROOT = selected_suite().root  # Schema从当前候选Skill读取，不接受调用方任意根目录。
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# 上下文对象
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ExecutionContextV5:
    """ExecutionContextV5 的不可变运行时表示。"""

    schema_version: str  # 固定为 ui-test.execution-context.v5
    session_id: str  # 当前pytest宿主进程唯一会话ID
    execution_origin: str  # pycharm | codex-cli | cli | ci | unknown
    origin_evidence: dict[str, Any]  # 来源证据摘要，不含绝对路径
    run_id: str  # 所有正式节点必须在BrowserContext前获得唯一Run ID
    node_id: str  # pytest nodeid
    case_id: str  # 稳定 Source Case ID
    branch_id: str  # 稳定 Source Case branch ID
    risk_level: str  # r0|r1|r2|r3
    environment: str  # 已通过v2.1校验的项目环境
    approved: bool  # 当前节点是否获得候选批准
    approval_source: str  # explicit-cli | pycharm-project-policy | not-approved
    runner_digest: str  # 当前stable test item的内容摘要
    project_config_digest: str  # 正式loader计算的配置摘要
    finalization_policy_digest: str  # 事务契约策略摘要
    attempt_ref: str  # 与append-only attempt目录一致的相对引用
    finalization_contract: str  # transaction-v1
    run_result_contract: str  # v5
    session_result_contract: str  # v1
    acceptance_contract: str  # external-exit-v1
    execution_channel: str
    config_summary: dict[str, Any]  # 已验证v2.1策略快照


@dataclass(frozen=True)
class _DispatchedContext(_ExecutionContextV5):
    task_ref: str
    batch_ref: str


#: 每个 item 存放其 ExecutionContextV2 的 stash key。
EXECUTION_CONTEXT_KEY: pytest.StashKey[_ExecutionContextV5] = pytest.StashKey()

#: marker 校验失败时存放错误码的 stash key，供 pytest_runtest_setup 使用。
_MARKER_ERROR_KEY: pytest.StashKey[str] = pytest.StashKey()

_SCOPE_LOCKS: pytest.StashKey[ExitStack] = pytest.StashKey()  # 同一节点可受多个决定约束。
_SESSION_TIME: pytest.StashKey[str] = pytest.StashKey()  # 重投使用同一自动编号。
_NOT_EXECUTED: pytest.StashKey[str] = pytest.StashKey()


_RUN_TARGET_KEY: pytest.StashKey[Mapping[str, Any]] = pytest.StashKey()
_ATTEMPT_OWNER_KEY: pytest.StashKey[ExitStack] = pytest.StashKey()

#: ST-006：每个 item 的 ExecutionAttemptStore 存放的 stash key。
_ATTEMPT_STORE_KEY: pytest.StashKey[Any] = pytest.StashKey()

#: ST-006：每个 item 的 attempt 已创建标志。
_ATTEMPT_STARTED_KEY: pytest.StashKey[bool] = pytest.StashKey()
_VERSION_BINDING_KEY: pytest.StashKey[dict] = pytest.StashKey()

#: ST-006：保存setup/call/teardown三阶段TestReport，用于唯一terminal判定。
_PHASE_REPORTS_KEY: pytest.StashKey[dict[str, pytest.TestReport]] = pytest.StashKey()

#: pytest进程级session与节点终态投影；仅用于sessionfinish写入只读结果。
_SESSION_ID_KEY: pytest.StashKey[str] = pytest.StashKey()
_SESSION: pytest.StashKey[FormalSession] = pytest.StashKey()
_PROJECT: pytest.StashKey[Mapping] = pytest.StashKey()
_SESSION_EVIDENCE_ROOT_KEY: pytest.StashKey[str] = pytest.StashKey()


# ---------------------------------------------------------------------------
# 受控 hookspec：根 conftest 提供项目配置与身份 resolver
# ---------------------------------------------------------------------------


def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    """注册本插件提供的 hookspec，让根 conftest 实现 project_config 与 identity resolver。"""
    pluginmanager.add_hookspecs(_UiTestExecutionHooks)


class _UiTestExecutionHooks:
    """受控接口：根 conftest 通过实现这些 hook 提供项目配置与身份 resolver。"""

    @pytest.hookspec(firstresult=True)
    def pytest_ui_test_project_config_path(self) -> str | None:
        """返回当前项目的 2.3 配置路径；未提供时插件不构建 config_summary。"""
        return None

    @pytest.hookspec(firstresult=True)
    def pytest_ui_test_execution_evidence_root(self) -> str | None:
        """返回execution evidence根目录；ST-006用于创建attempt文件。

        未提供时插件不创建attempt文件，仅收集diagnostics。
        """
        return None

    @pytest.hookspec(firstresult=True)
    def pytest_ui_test_finalize_run_result_v4(
        self,
        run_id: str,
        node_id: str,
        attempt_store: Any,
    ) -> dict[str, Any] | None:
        """ST-008：terminal后项目finalizer hookspec。

        只有create_terminal和attempt最终hash成功后才调用；
        finalizer失败必须使teardown失败。
        项目finalizer验证context/attempt/approval/pending/build/node一致，
        读取activation readiness，生成不可变run-result.json和evidence-index.json。
        """
        return None

    @pytest.hookspec(firstresult=True)
    def pytest_ui_test_finalization_target_v1(
        self,
        run_id: str,
        node_id: str,
        attempt_store: Any,
    ) -> dict[str, Any] | None:
        """返回受控run_root与逻辑引用；不得在此构建或发布结果。"""
        return None

    @pytest.hookspec(firstresult=True)
    def pytest_ui_test_build_finalization_candidate_v1(
        self,
        run_id: str,
        node_id: str,
        transaction_id: str,
        pre_terminal_events_hash: str,
        pytest_phase_status: Mapping[str, str],
        attempt_store: Any,
    ) -> dict[str, Any] | None:
        """项目适配器只返回RunResultV5/evidence-index候选，不得自行提交文件。"""
        return None


# ---------------------------------------------------------------------------
# CLI 参数注册
# ---------------------------------------------------------------------------

_OPTION_RUN_ID = "--ui-run-id"
_OPTION_R2_APPROVED = "--ui-r2-approved"
_OPTION_EXECUTION_ORIGIN = "--ui-execution-origin"


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册 ui-run-id、ui-r2-approved 和 ui-execution-origin 三个 CLI 参数。

    与现有项目参数保持兼容：重复注册必须可诊断（pytest 自身处理 OptionGroup 冲突），
    本插件使用唯一前缀 ``--ui-`` 避免与项目私有参数碰撞。
    """
    group = parser.getgroup("ui-test-execution", "UI-Test Execution Context")
    group.addoption("--ui-batch-id", help="Label this batch; each selected node gets its own run ID.")
    group.addoption(
        _OPTION_RUN_ID,
        action="store",
        default=None,
        help="显式 Run ID；CLI/CI/Codex 必须提供，PyCharm 可自动生成。",
    )
    group.addoption("--ui-write-budget", help="Reviewed formal batch limits in the project")
    group.addoption("--ui-write-budget-sha256", help="Approved SHA-256 of the exact budget bytes")
    group.addoption(
        _OPTION_R2_APPROVED,
        action="store_true",
        default=False,
        help="显式 R2 批准标志；非 PyCharm 入口必须显式提供。",
    )
    group.addoption(
        _OPTION_EXECUTION_ORIGIN,
        action="store",
        default=None,
        choices=["codex-cli"],
        help="仅供Codex受控入口声明来源；PyCharm必须由真实runner路径识别。",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    """Keep release contents immutable while pytest imports a selected release module."""
    import sys
    file = collector.path
    if file.name == "playwright-test.py" and file.parent.parent.name == "releases":
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            yield
        finally:
            sys.dont_write_bytecode = previous
    else:
        yield


def pytest_configure(config: pytest.Config) -> None:
    """注册正式marker，避免项目依赖外部pytest.ini才能解释测试身份。"""

    release_files = {Path(str(arg).partition("::")[0]).resolve() for arg in config.args
                     if Path(str(arg).partition("::")[0]).name == "playwright-test.py"}
    if len(release_files) > 1 and config.option.importmode == "prepend":
        # Each immutable release exports the same filename. Keep their module identities distinct.
        config.option.importmode = "importlib"
    worker = getattr(config, "workerinput", {})
    config.stash[_SESSION_ID_KEY] = worker.get("ui_test_session_id") or "SESSION-" + uuid.uuid4().hex.upper()
    config.stash[_SESSION_TIME] = worker.get("ui_test_session_time") or _utc_now()
    if os.environ.get("UI_TEST_CODEX_TASK_REF"):
        if not config.pluginmanager.hasplugin("ui_test_core.codex_pytest_dispatch"):
            raise pytest.UsageError("E_CODEX_USE_TASK_DISPATCHER")
        config._ui_test_dispatch_session = config.stash[_SESSION_ID_KEY]
    config.stash[_SESSION] = FormalSession()
    config.pluginmanager.register(config.stash[_SESSION])
    batch = config.getoption("--ui-batch-id")
    if batch is not None and not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", batch):
        raise pytest.UsageError("Invalid --ui-batch-id")

    output = getattr(config.option, "output", None)
    if output:
        session_id = getattr(config, "workerinput", {}).get("ui_test_session_id", config.stash[_SESSION_ID_KEY])
        instance = uuid.uuid4().hex  # Worker names can be reused after a crash.
        config.option.output = str(Path(output) / session_id / instance)

    markers = {
        "ui_test": "正式UI-Test节点",
        "case_id(value)": "稳定Source Case标识",
        "branch_id(value)": "稳定branch标识",
        "r0": "只读公开风险；formal_result=True 使用零提交 V5 事务",
        "r1": "只读认证风险",
        "r2": "测试环境可见UI单写风险",
        "r3": "禁止执行的高风险",
    }
    for marker, description in markers.items():
        config.addinivalue_line("markers", f"{marker}: {description}")  # 插件加载即建立同源marker契约。


# ---------------------------------------------------------------------------
# Marker 解析与校验
# ---------------------------------------------------------------------------

_RISK_MARKERS = ("r0", "r1", "r2", "r3")  # 风险等级 marker，每个 ui_test item 必须有且仅有一个。
_RISK_LEVELS = {
    "r0": "r0-read-only",
    "r1": "r1-read-only-authenticated",
    "r2": "r2-ui-write-test",
    "r3": "r3-high-impact",
}


class _MarkerError(Exception):
    """ui_test marker 校验失败，在 BrowserContext 前失败。"""

    def __init__(self, node_id: str, code: str) -> None:
        self.node_id = node_id
        self.code = code
        super().__init__(f"{code}:{node_id}")


def _parse_ui_test_markers(item: pytest.Item) -> dict[str, Any]:
    """从 item 的 marker 中提取 case_id、branch_id 和 risk_level。

    要求唯一风险与身份；缺失/冲突在 BrowserContext 前失败。
    """
    node_id = item.nodeid
    marker = item.get_closest_marker("ui_test")
    if marker is None:
        # 非 ui_test item 不被影响，返回空标识。
        return {"is_ui_test": False}

    # case_id 必须存在且唯一。
    case_markers = list(item.iter_markers("case_id"))
    if len(case_markers) == 0:
        raise _MarkerError(node_id, "E_UI_TEST_CASE_ID_MISSING")
    if len(case_markers) > 1:
        raise _MarkerError(node_id, "E_UI_TEST_CASE_ID_DUPLICATE")
    case_id = case_markers[0].args[0]
    if not isinstance(case_id, str) or not case_id:
        raise _MarkerError(node_id, "E_UI_TEST_CASE_ID_INVALID")

    # branch_id 必须存在且唯一。
    branch_markers = list(item.iter_markers("branch_id"))
    if len(branch_markers) == 0:
        raise _MarkerError(node_id, "E_UI_TEST_BRANCH_ID_MISSING")
    if len(branch_markers) > 1:
        raise _MarkerError(node_id, "E_UI_TEST_BRANCH_ID_DUPLICATE")
    branch_id = branch_markers[0].args[0]
    if not isinstance(branch_id, str) or not branch_id:
        raise _MarkerError(node_id, "E_UI_TEST_BRANCH_ID_INVALID")

    # 风险 marker 必须有且仅有一个。
    found_risks = [name for name in _RISK_MARKERS if list(item.iter_markers(name))]
    if len(found_risks) == 0:
        raise _MarkerError(node_id, "E_UI_TEST_RISK_MARKER_MISSING")
    if len(found_risks) > 1:
        raise _MarkerError(node_id, "E_UI_TEST_RISK_MARKER_CONFLICT")
    risk_level = _RISK_LEVELS[found_risks[0]]

    return {
        "is_ui_test": True,
        "case_id": case_id,
        "branch_id": branch_id,
        "risk_level": risk_level,
    }


# ---------------------------------------------------------------------------
# 上下文构建辅助
# ---------------------------------------------------------------------------

def _sha256_text(value: str) -> str:
    """返回带算法前缀的稳定摘要。"""
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _build_config_summary(config: Mapping[str, Any]) -> dict[str, Any]:
    """从当前或兼容项目配置提取 ExecutionContextV5 的契约快照。"""
    policy = config.get("pycharm_manual_execution") if isinstance(config.get("pycharm_manual_execution"), Mapping) else {}
    return {
        "schema_version": config["schema_version"],
        "contract_version": policy["contract_version"],
        "origin_detection": policy["origin_detection"],
        "entry_scope": policy["entry_scope"],
        "r2_authorization": policy["r2_authorization"],
        "run_scope": policy["run_scope"],
        "effective_concurrency": config["effective_concurrency"],
        "finalization_contract": policy["finalization_contract"],
        "run_result_contract": policy["run_result_contract"],
        "session_result_contract": "v2",
        "acceptance_contract": policy["acceptance_contract"],
    }


def _build_execution_context(
    *,
    item: pytest.Item,
    marker_info: dict[str, Any],
    config: pytest.Config,
    pycharm_config: Mapping[str, Any] | None,
) -> _ExecutionContextV5:
    """为单个 ui_test item 构建 ExecutionContextV5 并存入 item.stash。

    从所选文件获取实际来源摘要，核对当前运行授权。本 Story 不获取 R2 锁、不创建 attempt 文件。
    """
    node_id = item.nodeid
    case_id = marker_info["case_id"]
    branch_id = marker_info["branch_id"]
    risk_level = marker_info["risk_level"]

    # CLI 参数
    requested_run_id = config.getoption(_OPTION_RUN_ID, None) or None
    if len(config.stash[_SESSION].expected) > 1:
        if requested_run_id:
            raise _MarkerError(node_id, "E_MULTI_NODE_RUN_ID: use --ui-batch-id instead of --ui-run-id")
        seed = f"{config.stash[_SESSION_ID_KEY]}:{node_id}"
        requested_run_id = "UIT-" + hashlib.sha256(seed.encode()).hexdigest()[:32].upper()
    explicitly_approved = bool(config.getoption(_OPTION_R2_APPROVED, False)) and not _formal_read_only(item)
    declared_origin = config.getoption(_OPTION_EXECUTION_ORIGIN, None) or None

    if pycharm_config is None:
        raise _MarkerError(node_id, "E_UI_TEST_PROJECT_CONFIG_REQUIRED")
    config_summary = _build_config_summary(pycharm_config)  # 正式loader已完成v2.1与敏感字段校验。
    from ui_test_core.stage_write_budget import select_stage_budget
    budget = select_stage_budget(pycharm_config, case_id, branch_id, risk_level)
    if budget is not None:
        config_summary["stage_write_budget"] = budget
    project_config_digest = pycharm_config.get("config_fingerprint")
    if not isinstance(project_config_digest, str) or not _SHA256.fullmatch(project_config_digest):
        raise _MarkerError(node_id, "E_UI_TEST_PROJECT_CONFIG_DIGEST_INVALID")

    # 调用 ST-002 resolver 计算来源、Run ID 和候选批准。
    resolver_result = resolve_pycharm_run_context(
        config=pycharm_config or {},
        case_id=case_id,
        branch_id=branch_id,
        node_id=node_id,
        risk_level=risk_level,
        requested_run_id=requested_run_id,
        explicitly_approved=explicitly_approved,
        declared_origin=declared_origin,
        now=datetime.fromisoformat(config.stash[_SESSION_TIME]),
        unique_suffix=config.stash[_SESSION_ID_KEY][-8:],
        controller_origin=getattr(config, "workerinput", {}).get("ui_test_origin"),
    )

    if not isinstance(resolver_result.get("run_id"), str) or not resolver_result["run_id"]:
        raise _MarkerError(node_id, "E_FORMAL_RUN_ID_REQUIRED")  # 正式上下文不得携带Schema不允许的空Run ID。

    if risk_level == "r2-ui-write-test" and resolver_result["environment"] != "test":
        raise _MarkerError(node_id, "E_UI_TEST_R2_TEST_ENVIRONMENT_REQUIRED")
    if risk_level == "r2-ui-write-test" and not resolver_result["approved"] and not config.getoption("--ui-pre-submit-only", False):
        raise _MarkerError(node_id, "E_UI_TEST_R2_APPROVAL_REQUIRED")
    runner_path = Path(str(item.path)).resolve()
    selected = False
    arguments = config.args if config.args_source is pytest.Config.ArgsSource.ARGS else ()
    for argument in arguments:
        path_arg, _, node_suffix = str(argument).partition("::")
        candidate = (config.invocation_params.dir / path_arg).resolve()
        if candidate == runner_path and (
            not node_suffix or item.nodeid.endswith("::" + node_suffix)
            or ("::" + node_suffix + "::") in item.nodeid
            or item.nodeid.split("[", 1)[0].endswith("::" + node_suffix)
        ):
            selected = True
            break
    if not selected or runner_path.suffix.lower() != ".py":
        raise _MarkerError(node_id, "E_UI_TEST_EXPLICIT_RUNNER_REQUIRED")
    try:
        runner_digest = _sha256_bytes(runner_path.read_bytes())
    except OSError as exc:
        raise _MarkerError(node_id, "E_UI_TEST_RUNNER_UNREADABLE") from exc

    session_id = config.stash.get(_SESSION_ID_KEY, "")
    contract_material = {
        key: config_summary[key]
        for key in (
            "schema_version", "contract_version", "finalization_contract",
            "run_result_contract", "session_result_contract", "acceptance_contract",
        )
    }
    contract_material["effective_concurrency"] = config_summary["effective_concurrency"]
    if budget is not None:
        contract_material["stage_write_budget"] = budget
    context = _ExecutionContextV5(
        schema_version="ui-test.execution-context.v5",
        session_id=session_id,
        execution_origin=resolver_result["execution_origin"],
        origin_evidence=resolver_result["origin_evidence"],
        run_id=resolver_result["run_id"],
        node_id=node_id,
        case_id=case_id,
        branch_id=branch_id,
        risk_level=risk_level,
        environment=resolver_result.get("environment"),
        approved=resolver_result["approved"],
        approval_source=resolver_result["approval_source"],
        runner_digest=runner_digest,
        project_config_digest=project_config_digest,
        finalization_policy_digest=_sha256_text(
            json.dumps(contract_material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        ),
        attempt_ref="attempts/" + derive_attempt_directory_name(
            run_id=resolver_result["run_id"], node_id=node_id
        ),  # 上下文引用必须与实际attempt目录完全一致。
        finalization_contract=config_summary["finalization_contract"],
        run_result_contract=config_summary["run_result_contract"],
        session_result_contract=config_summary["session_result_contract"],
        acceptance_contract=config_summary["acceptance_contract"],
        execution_channel="xdist-worker" if hasattr(config, "workerinput") else "single-process",
        config_summary=config_summary,
    )
    intent = getattr(config, "_ui_test_codex_request", None)
    if intent:
        context = _DispatchedContext(**asdict(context), task_ref=intent["task_ref"], batch_ref=intent["batch_ref"])
    context_schema = json.loads((SKILL_ROOT / "schemas" / "execution-context-v5.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(context_schema).iter_errors(asdict(context)), key=lambda error: list(error.absolute_path))
    if errors:
        raise _MarkerError(node_id, "E_UI_TEST_EXECUTION_CONTEXT_SCHEMA_INVALID")
    item.stash[EXECUTION_CONTEXT_KEY] = context
    return context


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------


def _record_gate_diagnostic(
    *, store: ExecutionAttemptStore | None, item: pytest.Item, code: str, detail: str
) -> str:
    """记录早期拒绝；存储不可用时返回更强的fail-closed错误码。"""
    if store is None:
        return "E_UI_TEST_EVIDENCE_STORE_REQUIRED"
    try:
        store.append_diagnostics(run_id="unknown", node_id=item.nodeid, code=code, detail=detail)
    except ExecutionAttemptStoreError:
        return "E_UI_TEST_DIAGNOSTICS_WRITE_FAILED"
    return code


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """对每个 ui_test item 解析 marker 并构建 ExecutionContextV2 存入 item.stash。

    非 ui_test 普通 pytest 用例不受影响。marker 缺失/冲突不在此处 fail，
    而是存入 _MARKER_ERROR_KEY，由 pytest_runtest_setup 在 item 执行前失败。

    ST-005：R3 item 存入 E_R3_BLOCKED 错误码。
    ST-006：collection阶段身份/配置/门禁错误写diagnostics且不创建attempt。
    """
    hookrelay = session.config.hook
    project_config_path = hookrelay.pytest_ui_test_project_config_path()
    pycharm_config: Mapping[str, Any] | None = None
    config_error: str | None = None
    if isinstance(project_config_path, str) and project_config_path:
        try:
            pycharm_config = load_project_config(project_config_path, purpose="execute")  # 正式执行必须通过v2.1 loader。
        except ProjectConfigError as exc:
            config_error = str(exc).split(":", 1)[0]
    else:
        config_error = "E_UI_TEST_PROJECT_CONFIG_REQUIRED"

    # ST-006：获取execution evidence root，用于写入diagnostics。
    evidence_root = hookrelay.pytest_ui_test_execution_evidence_root()
    attempt_store: ExecutionAttemptStore | None = None
    if isinstance(evidence_root, str) and evidence_root:
        config.stash[_SESSION_EVIDENCE_ROOT_KEY] = evidence_root
        try:
            attempt_store = ExecutionAttemptStore(evidence_root=evidence_root)
        except ExecutionAttemptStoreError:
            attempt_store = None  # ui_test item稍后以稳定错误码fail closed。

    for item in items:
        try:
            marker_info = _parse_ui_test_markers(item)
        except _MarkerError as exc:
            # marker 缺失/冲突：存入错误码，由 runtest_setup 在 BrowserContext 前失败。
            item.stash[_MARKER_ERROR_KEY] = _record_gate_diagnostic(
                store=attempt_store, item=item, code=exc.code, detail="marker-gate"
            )
            continue
        if not marker_info.get("is_ui_test"):
            continue  # 非 ui_test item 不被影响。
        if attempt_store is None:
            item.stash[_MARKER_ERROR_KEY] = "E_UI_TEST_EVIDENCE_STORE_REQUIRED"
            continue  # 正式节点没有两级留痕根时不得静默执行。
        # ST-005：R3 item 在BrowserContext前报E_R3_BLOCKED。
        if marker_info["risk_level"] == "r3-high-impact":
            item.stash[_MARKER_ERROR_KEY] = _record_gate_diagnostic(
                store=attempt_store, item=item, code="E_R3_BLOCKED", detail="r3-gate"
            )
            continue
        if config_error is not None:
            item.stash[_MARKER_ERROR_KEY] = _record_gate_diagnostic(
                store=attempt_store, item=item, code=config_error, detail="config-gate"
            )
            continue
        item.stash[_PROJECT] = pycharm_config
        item.stash[_ATTEMPT_STORE_KEY] = attempt_store


def _deny_budget_before_attempt(item, code):
    item.stash[_NOT_EXECUTED] = code  # The protected attempt and all project fixtures have not started.
    pytest.fail(code, pytrace=False)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """在 item 执行前检查 marker 错误码，确保在 BrowserContext 前失败。

    先检查有效串行范围，再取得本次 attempt 的独占所有权。
    """
    # 重复投递可能复用 item，清除上次准入的状态，防止再次写入其终态。
    for key in (_ATTEMPT_STARTED_KEY, _PHASE_REPORTS_KEY, _NOT_EXECUTED, _RUN_TARGET_KEY, _VERSION_BINDING_KEY):
        if key in item.stash:
            del item.stash[key]
    error_code = item.stash.get(_MARKER_ERROR_KEY, None)
    if error_code is not None:
        pytest.fail(error_code, pytrace=False)

    context = None
    if _PROJECT in item.stash:
        try:
            context = _build_execution_context(item=item, marker_info=_parse_ui_test_markers(item),
                                               config=item.config, pycharm_config=item.stash[_PROJECT])
        except _MarkerError as exc:
            code = _record_gate_diagnostic(store=item.stash[_ATTEMPT_STORE_KEY], item=item,
                                           code=exc.code, detail="context-gate")
            pytest.fail(code, pytrace=False)
    if context is not None:
        config = item.stash[_PROJECT]  # 使用创建上下文时已校验的同一配置快照。
        from ui_test_core.artifact_layout import ProjectLayout, batch_stage_id
        evidence_root = item.config.stash.get(_SESSION_EVIDENCE_ROOT_KEY, None)
        project = ProjectLayout.from_evidence(Path(evidence_root) / "sessions") if evidence_root else None
        if project:
            stage_id = (batch_stage_id(context.task_ref, context.batch_ref)
                        if isinstance(context, _DispatchedContext) else context.session_id)
            project.reserve_run("playwright", stage_id)
        locks = ExitStack()
        item.stash[_SCOPE_LOCKS] = locks
        from copy import deepcopy
        from ui_test_core.formal_write_budget import ItemBudget, bind_item
        budget_path = item.config.getoption("--ui-write-budget")
        budget_sha = item.config.getoption("--ui-write-budget-sha256")
        formal_entry = os.environ.get("UI_TEST_REQUIRE_FORMAL_V5") == "1"
        if budget_path or budget_sha or formal_entry:
            authorized = context.approved and context.risk_level == "r2-ui-write-test"
            if authorized and not (budget_path and budget_sha):
                _deny_budget_before_attempt(item, "E_FORMAL_BUDGET_REQUIRED")
            phases = context.config_summary.get("stage_write_budget", {}).get("phase_ids", ["single"])
            bound = ItemBudget(Path(budget_path or "."), budget_sha, item.config.getoption("--ui-batch-id"),
                               getattr(context, "task_ref", None), Path.cwd() / "临时" / "formal-write-permits", context.run_id, item.nodeid,
                               context.case_id, context.branch_id, tuple(phases) if authorized else (),
                               deepcopy(context.config_summary.get("stage_write_budget")))
            if authorized:
                if not bound.path.resolve().is_relative_to(Path.cwd().resolve()):
                    _deny_budget_before_attempt(item, "E_FORMAL_BUDGET_PROJECT")

                try:
                    bound.check()
                except (OSError, ValueError) as exc:
                    code = str(exc) if str(exc).startswith('E_FORMAL_BUDGET_') else 'E_FORMAL_BUDGET_INVALID'
                    _deny_budget_before_attempt(item, code)
            locks.enter_context(bind_item(bound))
        for decision in config["effective_concurrency"]["serial_constraints"]:
            nodes = tuple(decision.get("node_ids", ()))
            if nodes and item.nodeid not in nodes:
                continue
            try:
                locks.enter_context(create_r2_project_lock(config=config, node_ids=nodes))
            except R2ProjectLockError as exc:
                locks.close()  # 立即释放先前已取得的重叠范围。
                if exc.code == "E_R2_PROJECT_LOCK_HELD":
                    scope = ", ".join(nodes) if nodes else "project-environment"
                    reason = f"该范围被占用，本次未执行 [{scope}] ({decision['decision_ref']})"
                    item.stash[_NOT_EXECUTED] = reason
                    pytest.fail(reason, pytrace=False)
                pytest.fail(exc.code, pytrace=False)

    attempt_store = item.stash.get(_ATTEMPT_STORE_KEY, None)
    if attempt_store is not None and context is not None:
        try:
            owner = ExitStack()
            owner.enter_context(attempt_store.attempt_ownership(run_id=context.run_id, node_id=context.node_id, case_id=context.case_id))
            item.stash[_ATTEMPT_OWNER_KEY] = owner
            attempt_store.create_attempt_start(
                run_id=context.run_id,
                node_id=context.node_id,
                case_id=context.case_id,
                branch_id=context.branch_id,
                risk_level=context.risk_level,
                execution_origin=context.execution_origin,
                approval_source=context.approval_source,
                runner_digest=context.runner_digest,
                project_config_digest=context.project_config_digest,
                schema_version="ui-test.execution-attempt.v2",
                session_id=context.session_id,
                finalization_mode=(
                    "not_applicable_qualification"
                    if bool(item.config.getoption("--ui-pre-submit-only", False))
                    else "transaction-v1"
                    if context.risk_level == "r2-ui-write-test" or _formal_read_only(item)
                    else "not_applicable_read_only"
                ),
            )
            item.stash[_ATTEMPT_STARTED_KEY] = True
            # ST-008：plugin在attempt-start之后写context，任何失败使pytest失败。
            document = asdict(context)
            if project and Path(item.path).resolve().is_relative_to(project.root):
                from ui_test_core.execution_version import bind_python
                supporting = [parent / "conftest.py" for parent in Path(item.path).resolve().parents
                              if parent.is_relative_to(project.root) and (parent / "conftest.py").is_file()]
                document["binding"] = bind_python(project.root, item.path, item.nodeid, supporting,
                                                  owner=(context.case_id, context.branch_id),
                                                  runner_digest=context.runner_digest)
                item.stash[_VERSION_BINDING_KEY] = document["binding"]
            attempt_store.write_execution_context(
                run_id=context.run_id,
                node_id=context.node_id,
                context_document=document,
            )
            target = item.config.hook.pytest_ui_test_finalization_target_v1(
                run_id=context.run_id, node_id=context.node_id, attempt_store=attempt_store)
            if isinstance(target, Mapping) and isinstance(target.get("run_root"), str):
                run_root = str(Path(target["run_root"]).resolve())
                attempt_store.bind_run_target(run_id=context.run_id, node_id=context.node_id, run_root=run_root)
                item.stash[_RUN_TARGET_KEY] = {**target, "run_root": run_root}
            if project:
                from ui_test_core.formal_catalog import attempt_checkpoint
                attempt_checkpoint(stage_id, evidence_root, context, attempt_store, "running")
            # 记录setup阶段admitted事件。
            attempt_store.append_event(
                run_id=context.run_id,
                node_id=context.node_id,
                event_type="attempt_started",
                phase="setup",
                code="ATTEMPT_STARTED",
            )
        except Exception as exc:
            # attempt-start创建失败不得伪造成功；存入错误码供后续处理。
            code = getattr(exc, "code", "E_ATTEMPT_START_FAILED")
            if code == "E_ATTEMPT_START_ALREADY_EXISTS":
                item.stash[_NOT_EXECUTED] = code  # 保留原获准执行的终态，另记重复投递。
            item.stash[_MARKER_ERROR_KEY] = code
            pytest.fail(code, pytrace=False)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item: pytest.Item):
    """Release ownership after teardown reports and terminal publication have completed."""
    try:
        yield
    finally:
        owner = item.stash.get(_ATTEMPT_OWNER_KEY, None)
        if owner is not None:
            owner.close()
        _release_r2_lock(item)  # 报告 hook 中断时也释放约束。


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    """只包裹真实fixture teardown；R2锁延迟到finalization结束后释放。"""
    yield


def _formal_read_only(item: pytest.Item) -> bool:
    marker = item.get_closest_marker("r0")
    return marker is not None and marker.kwargs.get("formal_result") is True


def _terminal_status_from_reports(reports: Mapping[str, pytest.TestReport]) -> str:
    """从pytest真实三阶段报告推导attempt终态，不读取或持久化原始异常。"""
    failed = [report for report in reports.values() if report.failed]
    if failed:
        failure_text = " ".join(str(report.longrepr).lower() for report in failed)
        if "timeout" in failure_text or "timed out" in failure_text:
            return "timed_out"
        if "keyboardinterrupt" in failure_text or "cancelled" in failure_text:
            return "cancelled"
        return "failed"
    if any(report.skipped for report in reports.values()):
        return "cancelled"
    if all(phase in reports for phase in ("setup", "call", "teardown")):
        return "passed"
    return "write_outcome_unknown"


def _stable_exception(exc: BaseException) -> tuple[str, str, str]:
    """把异常压缩成稳定错误码、异常类和消息摘要，不持久化原始消息。"""
    raw_code = getattr(exc, "code", None)
    if not isinstance(raw_code, str):
        raw_code = str(exc).split(":", 1)[0].strip()
    code = raw_code if re.fullmatch(r"E_[A-Z0-9_]+", raw_code or "") else "E_FINALIZER_FAILED"
    return code, type(exc).__name__, _sha256_text(str(exc))


def _release_r2_lock(item: pytest.Item) -> None:
    """finalization完成后释放锁；失败由调用方投影为治理错误。"""
    lock = item.stash.get(_SCOPE_LOCKS, None)
    if lock is None:
        return
    lock.close()
    del item.stash[_SCOPE_LOCKS]


def _record_session_node(
    *,
    item: pytest.Item,
    context: _ExecutionContextV5,
    attempt_store: ExecutionAttemptStore,
    finalization_status: str,
    receipt_ref: str | None = None,
    receipt_hash: str | None = None,
    receipt_document: Mapping | None = None,
) -> None:
    terminal = attempt_store.read_terminal(run_id=context.run_id, node_id=context.node_id)
    if terminal is None:
        return
    node = {
        "attempt_ref": context.attempt_ref,
        "run_id": context.run_id,
        "node_id": context.node_id,
        "terminal_ref": context.attempt_ref + "/terminal.json",
        "terminal_hash": canonical_hash(terminal),
        "finalization_status": finalization_status,
        "disposition": "passed" if terminal["status"] == "passed" else "failed",
        "_execution_origin": context.execution_origin,
        "_origin_evidence_digest": context.origin_evidence["evidence_digest"],
    }
    if receipt_ref and receipt_hash:
        node["receipt_ref"] = receipt_ref
        node["receipt_hash"] = receipt_hash
        if receipt_document is not None and receipt_ref.startswith("runs/"):
            # Project run roots may live outside the attempt store. Bind a portable receipt copy.
            root = Path(item.config.stash[_SESSION_EVIDENCE_ROOT_KEY])
            with io_path(root / context.attempt_ref / "session-receipt.json").open("x", encoding="utf-8") as stream:
                json.dump(receipt_document, stream, ensure_ascii=False)
    item.stash[_PHASE_REPORTS_KEY]["teardown"].ui_test_node = node
    evidence_root = item.config.stash.get(_SESSION_EVIDENCE_ROOT_KEY, None)
    if evidence_root:
        from ui_test_core.artifact_layout import batch_stage_id
        from ui_test_core.formal_catalog import attempt_checkpoint
        stage_id = batch_stage_id(context.task_ref, context.batch_ref) if isinstance(context, _DispatchedContext) else context.session_id
        target = item.stash.get(_RUN_TARGET_KEY, {})
        attempt_checkpoint(stage_id, evidence_root, context, attempt_store, node["disposition"],
                           target.get("run_root") if finalization_status == "committed" else None)


def _verify_current_run_links(run_result, root, context, attempt_store, events_hash, phase_status, binding=None):
    from ui_test_core.run_evidence_linker import verify_run_result_v5_links
    from ui_test_core.strict_json import load_strict_json

    ref, digest = attempt_store.read_execution_context_ref_and_hash(
        run_id=context.run_id, node_id=context.node_id
    )
    document = asdict(context)
    if binding is not None:
        document["binding"] = binding
    if digest != canonical_hash(document):
        raise FinalizationTransactionError("E_FINALIZATION_CONTEXT_LINK_MISMATCH")
    root = root.resolve(strict=True)
    for field in ("resolved_test_data_ref", "approval_ref"):
        relative = Path(str(run_result.get(field, "")))
        if relative.drive or relative.is_absolute() or ".." in relative.parts:
            raise FinalizationTransactionError("E_FINALIZATION_EVIDENCE_PATH_INVALID")
        if not (root / relative).resolve(strict=True).is_relative_to(root):
            raise FinalizationTransactionError("E_FINALIZATION_EVIDENCE_PATH_INVALID")
    approval = load_strict_json(root / run_result["approval_ref"])
    if context.risk_level == "r0-read-only":
        from ui_test_core.run_evidence_linker import build_read_only_boundary
        expected_boundary = build_read_only_boundary(asdict(context))
        if run_result.get("risk_level") != context.risk_level or canonical_hash(approval) != canonical_hash(expected_boundary):
            raise FinalizationTransactionError("E_FINALIZATION_READ_ONLY_BOUNDARY_MISMATCH")
    else:
        if run_result.get("risk_level") == "r0-read-only":
            raise FinalizationTransactionError("E_FINALIZATION_CONTEXT_LINK_MISMATCH")
        _verify_write_approval(approval, context)
    if any(run_result.get(key) != getattr(context, key) for key in ("case_id", "branch_id")):
        raise FinalizationTransactionError("E_FINALIZATION_CONTEXT_LINK_MISMATCH")
    issues = verify_run_result_v5_links(
        run_result, run_root=root, expected_session_id=context.session_id,
        expected_run_id=context.run_id, expected_node_id=context.node_id,
        expected_execution_context_ref=ref, expected_execution_context_hash=digest,
        expected_attempt_ref=context.attempt_ref, expected_pre_terminal_events_hash=events_hash,
        expected_approval_hash=canonical_hash(approval), expected_pytest_phase_status=phase_status,
    )
    if issues:
        raise FinalizationTransactionError(issues[0])


def _verify_write_approval(approval, context):
    if validate_document(approval, "r2-approval-record-v3.schema.json"):
        raise FinalizationTransactionError("E_FINALIZATION_APPROVAL_INVALID")
    budget = context.config_summary.get("stage_write_budget")
    expected = {
        "run_id": context.run_id, "case_id": context.case_id, "branch_id": context.branch_id,
        "node_id": context.node_id, "runner_digest": context.runner_digest, "decision": "approved",
        "risk_level": context.risk_level, "approval_source": context.approval_source,
        "environment": context.environment, "stage_write_budget": budget,
        "max_submit_count": len(budget["phase_ids"]) if budget else 1,
    }
    if any(approval.get(key) != value for key, value in expected.items()):
        raise FinalizationTransactionError("E_FINALIZATION_APPROVAL_LINK_MISMATCH")
    boundary_fields = ("run_id", "case_id", "environment", "allowed_action", "channel", "max_submit_count")
    if approval["boundary_hash"] != canonical_hash({key: approval[key] for key in boundary_fields}):
        raise FinalizationTransactionError("E_FINALIZATION_APPROVAL_BOUNDARY_MISMATCH")


def _fail_teardown_report(report: pytest.TestReport, *, code: str, exception_class: str, message_digest: str) -> None:
    """让原pytest/TeamCity进程看到稳定且非空的finalization longrepr。"""
    detail = f"{code} [{exception_class}; message_digest={message_digest}]"
    report.sections.append(("ui-test-governance", detail))
    report.longrepr = detail
    report.outcome = "failed"


def _archive_playwright_output(item, context, store):
    """Archive upstream screenshot/trace files before publishing any formal references."""
    source = (item.funcargs or {}).get("output_path")
    if not source:
        return
    folder = Path(source).resolve()
    leaf = Path(item.config.getoption("--output")).resolve()
    if folder.parent != leaf or not folder.is_dir():
        return
    artifacts = sorted(p for p in folder.iterdir() if re.fullmatch(
        r"trace(?:-[0-9]+)?\.zip|test-(?:finished|failed)-[0-9]+\.png", p.name))
    if not artifacts:
        return
    target = item.stash.get(_RUN_TARGET_KEY, None)
    if target is None:
        return  # No project-owned formal output root for this item.
    archive = io_path(target["run_root"]) / "playwright"
    archive.mkdir(parents=True, exist_ok=False)  # Never overwrite an earlier run's evidence.
    entries = []
    for artifact in artifacts:
        if artifact.resolve().parent != folder or not artifact.is_file():
            raise ValueError("E_PLAYWRIGHT_ARTIFACT_PATH")
        destination = archive / artifact.name
        digest = hashlib.sha256()
        with artifact.open("rb") as source_file, destination.open("xb") as target_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(chunk)
                target_file.write(chunk)
        entries.append({"ref": "playwright/" + artifact.name, "sha256": digest.hexdigest()})
    with (archive / "artifacts.json").open("x", encoding="utf-8") as index:
        json.dump(entries, index, sort_keys=True)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    """在其他makereport wrapper完成后执行事务，再决定唯一terminal。"""
    outcome = yield
    report: pytest.TestReport = outcome.get_result()
    if report.when == "setup" and _NOT_EXECUTED in item.stash:
        report.ui_test_not_executed = item.stash[_NOT_EXECUTED]
    context = item.stash.get(EXECUTION_CONTEXT_KEY, None)
    attempt_store = item.stash.get(_ATTEMPT_STORE_KEY, None)
    if context is None:
        return
    if attempt_store is None or not item.stash.get(_ATTEMPT_STARTED_KEY, False):
        if report.when == "teardown":
            try:
                _release_r2_lock(item)
            except Exception as exc:
                code, exception_class, message_digest = _stable_exception(exc)
                _fail_teardown_report(
                    report, code=code, exception_class=exception_class, message_digest=message_digest
                )
        return

    reports = item.stash.get(_PHASE_REPORTS_KEY, {})
    report.ui_test_run_id = context.run_id
    reports[report.when] = report
    item.stash[_PHASE_REPORTS_KEY] = reports
    try:
        attempt_store.append_event(
            run_id=context.run_id,
            node_id=context.node_id,
            event_type="executing",
            phase=report.when,
            code=f"PYTEST_{report.when.upper()}_{report.outcome.upper()}",
        )
    except ExecutionAttemptStoreError as exc:
        _fail_teardown_report(
            report,
            code=exc.code,
            exception_class=type(exc).__name__,
            message_digest=_sha256_text(str(exc)),
        )
        reports[report.when] = report

    if report.when != "teardown":
        return

    try:
        _archive_playwright_output(item, context, attempt_store)
    except Exception as exc:
        _fail_teardown_report(report, code="E_PLAYWRIGHT_ARCHIVE_FAILED",
                              exception_class=type(exc).__name__, message_digest=_sha256_text(str(exc)))

    terminal_status = _terminal_status_from_reports(reports)
    stage_failure = bool(context.config_summary.get("stage_write_budget")) and context.risk_level == "r2-ui-write-test" and not item.config.getoption("--ui-pre-submit-only", False)
    qualification_mode = bool(item.config.getoption("--ui-pre-submit-only", False))
    formal_read_only = _formal_read_only(item) and not qualification_mode
    if terminal_status != "passed" and not (stage_failure or formal_read_only):
        try:
            _release_r2_lock(item)
        except Exception as exc:
            code, exception_class, message_digest = _stable_exception(exc)
            terminal_status = "error"
            _fail_teardown_report(
                report, code=code, exception_class=exception_class, message_digest=message_digest
            )
        attempt_store.create_terminal(
            run_id=context.run_id,
            node_id=context.node_id,
            status=terminal_status,
            code=f"PYTEST_{terminal_status.upper()}",
        )
        _record_session_node(
            item=item,
            context=context,
            attempt_store=attempt_store,
            finalization_status="missing",
        )
        return

    read_only_mode = context.risk_level != "r2-ui-write-test"
    if qualification_mode or (read_only_mode and not formal_read_only):
        try:
            _release_r2_lock(item)
            attempt_store.create_terminal(
                run_id=context.run_id,
                node_id=context.node_id,
                status="passed",
                code="PYTEST_PASSED",
            )
            _record_session_node(
                item=item,
                context=context,
                attempt_store=attempt_store,
                finalization_status=(
                    "not_applicable_qualification" if qualification_mode else "not_applicable_read_only"
                ),
            )
        except Exception as exc:
            code, exception_class, message_digest = _stable_exception(exc)
            _fail_teardown_report(
                report, code=code, exception_class=exception_class, message_digest=message_digest
            )
        return

    transaction_id = "FIN-" + hashlib.sha256(
        f"{context.session_id}:{context.run_id}:{context.node_id}".encode("utf-8")
    ).hexdigest()[:24]
    transaction: FinalizationTransaction | None = None
    receipt_ref: str | None = None
    receipt_hash: str | None = None
    try:
        target = item.stash.get(_RUN_TARGET_KEY, None)
        if not isinstance(target, Mapping) or not isinstance(target.get("run_root"), str):
            raise FinalizationTransactionError("E_FINALIZATION_TARGET_REQUIRED")
        transaction = FinalizationTransaction(target["run_root"])
        attempt_store.append_event(
            run_id=context.run_id,
            node_id=context.node_id,
            event_type="finalization_started",
            phase="finalization",
            code="FINALIZATION_STARTED",
            transaction_id=transaction_id,
        )
        committed_event_time = _utc_now()
        planned_committed_event = {
            "event_type": "finalization_committed",
            "recorded_at": committed_event_time,
            "phase": "finalization",
            "code": "FINALIZATION_COMMITTED",
            "transaction_id": transaction_id,
        }
        pre_terminal_events_hash = attempt_store.compute_pre_terminal_hash(
            run_id=context.run_id,
            node_id=context.node_id,
            additional_events=[planned_committed_event],
        )
        phase_status = {
            phase: reports[phase].outcome if phase in reports else "unknown"
            for phase in ("setup", "call", "teardown")
        }
        candidate = item.config.hook.pytest_ui_test_build_finalization_candidate_v1(
            run_id=context.run_id,
            node_id=context.node_id,
            transaction_id=transaction_id,
            pre_terminal_events_hash=pre_terminal_events_hash,
            pytest_phase_status=phase_status,
            attempt_store=attempt_store,
        )
        if not isinstance(candidate, Mapping):
            raise FinalizationTransactionError("E_FINALIZATION_CANDIDATE_REQUIRED")
        if candidate.get("run_result", {}).get("stage_write_budget") != context.config_summary.get("stage_write_budget"):
            raise FinalizationTransactionError("E_FINALIZATION_STAGE_BUDGET_MISMATCH")
        run_result = candidate.get("run_result", {})
        if run_result.get("schema_version") == "ui-test.run-result.v5":
            _verify_current_run_links(
                run_result, transaction.run_root, context, attempt_store,
                pre_terminal_events_hash, phase_status, item.stash.get(_VERSION_BINDING_KEY, None),
            )
        committed = transaction.commit(
            transaction_id=transaction_id,
            run_id=context.run_id,
            node_id=context.node_id,
            run_result=candidate.get("run_result", {}),
            evidence_index=candidate.get("evidence_index", {}),
        )
        if committed.get("status") != "committed":
            raise FinalizationTransactionError("E_FINALIZATION_NOT_CURRENT_PROCESS_COMMITTED")
        manifest = committed["manifest"]
        receipt = committed["receipt"]
        attempt_store.append_event(
            run_id=context.run_id,
            node_id=context.node_id,
            event_type="finalization_committed",
            phase="finalization",
            code="FINALIZATION_COMMITTED",
            transaction_id=transaction_id,
            recorded_at=committed_event_time,
        )
        if attempt_store.compute_pre_terminal_hash(
            run_id=context.run_id, node_id=context.node_id
        ) != pre_terminal_events_hash:
            raise FinalizationTransactionError("E_FINALIZATION_PRE_TERMINAL_CLOSURE_MISMATCH")
        # 锁覆盖UI写与commit/receipt；在passed terminal前释放，使释放失败也不能留下passed终态。
        _release_r2_lock(item)
        commit_ref = f"runs/{context.run_id}/finalization/finalization-commit.json"
        receipt_ref = f"runs/{context.run_id}/finalization/finalization-receipt.json"
        commit_hash = canonical_hash(manifest)
        receipt_hash = canonical_hash(receipt)
        attempt_store.create_terminal(
            run_id=context.run_id,
            node_id=context.node_id,
            status=terminal_status,
            code="PYTEST_" + terminal_status.upper(),
            commit_manifest_ref=commit_ref,
            commit_manifest_hash=commit_hash,
            receipt_ref=receipt_ref,
            receipt_hash=receipt_hash,
            pre_terminal_events_hash=pre_terminal_events_hash,
            finalization_run_root=target["run_root"],
        )
        _record_session_node(
            item=item,
            context=context,
            attempt_store=attempt_store,
            finalization_status="committed",
            receipt_ref=receipt_ref,
            receipt_hash=receipt_hash,
            receipt_document=receipt,
        )
        return
    except Exception as exc:
        code, exception_class, message_digest = _stable_exception(exc)
        _fail_teardown_report(
            report, code=code, exception_class=exception_class, message_digest=message_digest
        )  # 先保证原helper可见，后续任何证据写失败都不能吞掉longrepr。
        if transaction is not None:
            try:
                failed = transaction.record_failure(
                    transaction_id=transaction_id,
                    session_id=context.session_id,
                    run_id=context.run_id,
                    node_id=context.node_id,
                    error_code=code,
                    exception_class=exception_class,
                    message_digest=message_digest,
                )
                receipt = failed["receipt"]
                receipt_ref = f"runs/{context.run_id}/finalization/finalization-receipt.json"
                receipt_hash = canonical_hash(receipt)
            except Exception:
                receipt_ref = None
                receipt_hash = None
        if receipt_ref is None or receipt_hash is None:
            try:
                receipt_ref, fallback_receipt = attempt_store.write_finalization_failure_receipt(
                    run_id=context.run_id,
                    node_id=context.node_id,
                    session_id=context.session_id,
                    transaction_id=transaction_id,
                    error_code=code,
                    exception_class=exception_class,
                    message_digest=message_digest,
                )
                receipt_hash = canonical_hash(fallback_receipt)
            except Exception as receipt_exc:
                report.sections.append((
                    "ui-test-governance",
                    "E_FINALIZATION_FAILURE_RECEIPT_WRITE_FAILED:" + _sha256_text(str(receipt_exc)),
                ))
        try:
            attempt_store.append_event(
                run_id=context.run_id,
                node_id=context.node_id,
                event_type="finalization_failed",
                phase="finalization",
                code=code,
                exception_class=exception_class,
                message_digest=message_digest,
                transaction_id=transaction_id,
            )
        except Exception as event_exc:
            report.sections.append((
                "ui-test-governance",
                "E_FINALIZATION_FAILURE_EVENT_WRITE_FAILED:" + _sha256_text(str(event_exc)),
            ))
        try:
            _release_r2_lock(item)
        except Exception as lock_exc:
            report.sections.append((
                "ui-test-governance",
                "E_R2_LOCK_RELEASE_FAILED:" + _sha256_text(str(lock_exc)),
            ))
        try:
            attempt_store.create_terminal(
                run_id=context.run_id,
                node_id=context.node_id,
                status="error",
                code=code,
                receipt_ref=receipt_ref or "",
                receipt_hash=receipt_hash or "",
            )
        except Exception as terminal_exc:
            report.sections.append((
                "ui-test-governance",
                "E_FINALIZATION_ERROR_TERMINAL_WRITE_FAILED:" + _sha256_text(str(terminal_exc)),
            ))
            return
        try:
            _record_session_node(
                item=item,
                context=context,
                attempt_store=attempt_store,
                finalization_status="failed" if receipt_ref and receipt_hash else "missing",
                receipt_ref=receipt_ref,
                receipt_hash=receipt_hash,
                receipt_document=receipt if receipt_ref and receipt_ref.startswith("runs/") else None,
            )
        except Exception as session_exc:
            report.sections.append((
                "ui-test-governance",
                "E_FINALIZATION_SESSION_NODE_WRITE_FAILED:" + _sha256_text(str(session_exc)),
            ))


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    config = node.config
    node.workerinput["ui_test_session_id"] = config.stash[_SESSION_ID_KEY]
    node.workerinput["ui_test_session_time"] = config.stash[_SESSION_TIME]
    node.workerinput["ui_test_origin"] = classify_execution_origin(
        declared_origin=config.getoption(_OPTION_EXECUTION_ORIGIN, None))
    # Local workers share the controller's pytest tempdir, isolated for every actual instance.
    node.workerinput["ui_test_manifest"] = str(config._tmp_path_factory.getbasetemp()
                                              / ("formal-" + uuid.uuid4().hex + ".json"))


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    config = session.config
    formal = [item.nodeid for item in session.items if item.get_closest_marker("ui_test")]
    config.stash[_SESSION].observe_collection([item.nodeid for item in session.items], formal)
    if formal and not config.option.collectonly and not hasattr(config, "_ui_test_codex_request"):
        from ui_test_core.artifact_layout import ProjectLayout
        from ui_test_core.formal_catalog import selected_cases, registration_notice
        from ui_test_core.stage_events import stage_started
        root = config.stash.get(_SESSION_EVIDENCE_ROOT_KEY, None)
        project = ProjectLayout.from_evidence(Path(root) / "sessions") if root else None
        if project:
            registration_notice(stage_started(project.root, "playwright", config.stash[_SESSION_ID_KEY],
                                              config.stash[_SESSION_TIME], selected_cases(session.items)))
    worker = getattr(config, "workerinput", {})
    if worker.get("ui_test_manifest"):
        Path(worker["ui_test_manifest"]).write_text(json.dumps(formal), encoding="utf-8")


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node, ids):
    config = node.config
    formal = json.loads(Path(node.workerinput["ui_test_manifest"]).read_text(encoding="utf-8"))
    config.stash[_SESSION].observe_collection(ids, formal)


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    if error is not None:
        node.config.stash[_SESSION].worker_errors.append(node.gateway.id)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    result = yield
    _write_session_result(session)
    return result


def _write_session_result(session):
    """写PytestSessionResultV2；只投影最终exit，不补写任何passed terminal。"""
    config = session.config
    state = config.stash[_SESSION]
    if hasattr(config, "workerinput") or config.option.collectonly or not state.expected:
        return
    nodes = state.records.values()
    expected = state.expected
    evidence_root = config.hook.pytest_ui_test_execution_evidence_root()
    if not evidence_root:
        session.exitstatus = session.exitstatus or pytest.ExitCode.INTERNAL_ERROR
        return
    try:
        origins = {node["_execution_origin"] for node in nodes}
        origin = next(iter(origins)) if len(origins) == 1 else "unknown"
        origin_digests = sorted({node["_origin_evidence_digest"] for node in nodes})
        public_nodes = state.reconcile(Path(evidence_root), config.stash[_SESSION_ID_KEY])
        selected = {item.nodeid: item for item in session.items}
        selected_cases = {}
        for node in public_nodes:
            item = selected.get(node["node_id"])
            if item is not None:
                for name in ("case_id", "branch_id"):
                    marker = item.get_closest_marker(name)
                    if marker and marker.args and isinstance(marker.args[0], str):
                        selected_cases.setdefault(node["node_id"], {})[name] = marker.args[0]
            if node["finalization_status"] != "committed":
                continue
            # Reopen the project's authoritative transaction after worker teardown.
            try:
                store = ExecutionAttemptStore(evidence_root=evidence_root)
                target = config.hook.pytest_ui_test_finalization_target_v1(
                    run_id=node["run_id"], node_id=node["node_id"],
                    attempt_store=store)
                if not store.matches_run_target(run_id=node["run_id"], node_id=node["node_id"],
                                                run_root=target["run_root"]):
                    raise ValueError("E_SESSION_RUN_TARGET_MISMATCH")
                closure = FinalizationTransaction(target["run_root"]).read_committed()
                if (closure and canonical_hash(closure["receipt"]) == node["receipt_hash"]
                        and (node["disposition"] != "passed" or closure["run_result"]["overall_status"] == "passed")):
                    if hasattr(config, "_ui_test_codex_request"):
                        if not hasattr(config, "_ui_test_codex_write_state"):
                            config._ui_test_codex_write_state = {}
                        config._ui_test_codex_write_state[node["node_id"]] = closure["run_result"]["write_state"]
                    continue
            except (ValueError, OSError, RuntimeError, TypeError, KeyError):
                pass
            node.update(disposition="unknown", finalization_status="missing", missing_reason="invalid-transaction")
            for field in ("terminal_ref", "terminal_hash", "receipt_ref", "receipt_hash"):
                node.pop(field, None)
        run_ids = [row.get("run_id") for row in public_nodes]
        all_committed = (len(run_ids) == len(set(run_ids)) and state.consistent and not state.worker_errors and
                         set(expected) == set(state.records)) and all(
            node["disposition"] == "passed" and node["finalization_status"] in {
                "committed", "not_applicable_qualification", "not_applicable_read_only"
            }
            for node in public_nodes
        )
        passed = not int(session.exitstatus) and all_committed and not state.denied_duplicate_nodes
        session_status = "passed" if passed else "failed"
        if session.exitstatus == pytest.ExitCode.INTERRUPTED:
            session_status = "interrupted"
        if session_status != "passed" and not int(session.exitstatus):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        document: dict[str, Any] = {
            "expected_nodes": expected,
            "collection_consistent": state.consistent,
            "worker_errors": state.worker_errors,
            "unexpected_nodes": sorted(set(state.records) - set(expected)),
            "schema_version": "ui-test.pytest-session-result.v2",
            "session_id": session.config.stash[_SESSION_ID_KEY],
            "execution_origin": origin,
            "origin_evidence_digest": (
                origin_digests[0]
                if len(origin_digests) == 1
                else canonical_hash({"origin_evidence_digests": origin_digests})
            ),
            "nodes": public_nodes,
            "pytest_exitstatus": int(session.exitstatus),
            "all_required_nodes_committed": all_committed,
            "session_status": session_status,
            "recorded_at": _utc_now(),
            "started_at": config.stash[_SESSION_TIME],
        }
        if selected_cases:
            document["selected_cases"] = selected_cases
        if state.denied_duplicate_nodes:
            document["denied_duplicate_nodes"] = sorted(state.denied_duplicate_nodes)
        if config.getoption("--ui-batch-id"):
            document["batch_id"] = config.getoption("--ui-batch-id")
        document["session_result_hash"] = canonical_hash(document)
        if validate_document(document, "pytest-session-result-v2.schema.json"):
            raise RuntimeError("E_PYTEST_SESSION_RESULT_SCHEMA_INVALID")
        target = io_path(Path(evidence_root) / "sessions" / f"{document['session_id']}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        pending = target.with_suffix(".tmp")
        with pending.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        pending.rename(target)
        if not hasattr(config, "_ui_test_codex_request"):  # Codex publishes once after all child sessions finish.
            from ui_test_core.stage_delivery import publish_session
            try:
                delivery = publish_session(target)
            except (OSError, ValueError, RuntimeError, ImportError) as error:
                message = f"E_STAGE_REPORT_VALIDATION: {error}"
                session.exitstatus = session.exitstatus or pytest.ExitCode.INTERNAL_ERROR
            else:
                message = f"UI-Test stage report: {delivery['report_url']}"
            terminal = config.pluginmanager.getplugin("terminalreporter")
            if terminal:
                terminal.write_line(message)
            else:
                print(message)
    except Exception:
        # SessionResult缺失必须反映到原helper退出码；恢复器也不得事后补成passed。
        session.exitstatus = pytest.ExitCode.INTERNAL_ERROR


@pytest.fixture
def ui_test_execution_context(request: pytest.FixtureRequest) -> _ExecutionContextV5:
    """function-scope fixture：项目 runtime 通过此 fixture 消费已验证上下文。

    不允许重新计算来源或批准。如果 item 没有 ui_test marker，fixture 报错。
    """
    context = request.node.stash.get(EXECUTION_CONTEXT_KEY, None)
    if context is None:
        pytest.fail("E_UI_TEST_CONTEXT_NOT_AVAILABLE: fixture requires ui_test marker", pytrace=False)
    return context
