"""核对已知共享状态冲突的用户接受记录，供同一任务准备并发时调用。"""
from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Scope:
    task_ref: str
    batch_ref: str
    nodes: frozenset[str]  # 实际展开的完整授权批次


@dataclass(frozen=True)
class Conflict:
    writer: str
    reader: str
    object_ref: str  # 同一项目、环境和业务对象的脱敏引用
    write_action: str
    read_action: str
    assertion: str
    evidence_refs: tuple[str, ...] = field(compare=False)  # 新增佐证不改变同一冲突


@dataclass(frozen=True)
class Acceptance:
    scope: Scope
    conflict: Conflict
    instruction_ref: str  # 明确接受这条冲突的用户消息


def accepted_instruction(scope: Scope, conflict: Conflict, decisions: Iterable[Acceptance]) -> str | None:
    """仅返回可追溯的冲突决定。调度入口独立核实原指令、项目策略和执行授权。"""
    fields = (scope.task_ref, scope.batch_ref, conflict.writer, conflict.reader,
              conflict.object_ref, conflict.write_action, conflict.read_action, conflict.assertion)
    if not all(value.strip() for value in fields) or not any(ref.strip() for ref in conflict.evidence_refs):
        return None
    if conflict.writer == conflict.reader or not {conflict.writer, conflict.reader} <= scope.nodes:
        return None
    for decision in decisions:
        if (decision.scope == scope and decision.conflict == conflict and decision.instruction_ref.strip()
                and any(ref.strip() for ref in decision.conflict.evidence_refs)):
            return decision.instruction_ref
    return None
