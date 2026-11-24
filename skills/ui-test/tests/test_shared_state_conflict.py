"""复用具体冲突决定时，以用户接受的同批范围及断言为准。"""
from dataclasses import replace

import pytest

from ui_test_core.shared_state_conflict import Acceptance, Conflict, Scope, accepted_instruction


A = "test_todo.py::test_complete[team]"
B = "test_todo.py::test_pending[team]"
C = "test_other.py::test_title"
scope = Scope("task-1", "batch-1", frozenset({A, B}))
conflict = Conflict(A, B, "team/todo/42", "complete", "read status", "pending",
                    ("visible:row-42", "case:B.step3"))
decision = Acceptance(scope, conflict, "message:12")


def test_reuses_explicit_decision_for_same_unordered_node_set():
    again = replace(scope, nodes=frozenset([B, A]))
    assert accepted_instruction(again, conflict, [decision]) == "message:12"


@pytest.mark.parametrize("new_scope,new_conflict", [
    (replace(scope, task_ref="task-2"), conflict),
    (replace(scope, batch_ref="batch-2"), conflict),
    (replace(scope, nodes=frozenset({A, B, C})), conflict),
    (scope, replace(conflict, object_ref="team/todo/43")),
    (scope, replace(conflict, write_action="delete")),
    (scope, replace(conflict, assertion="row exists")),
    (scope, replace(conflict, reader=C)),
])
def test_changed_scope_or_conflict_needs_own_decision(new_scope, new_conflict):
    assert accepted_instruction(new_scope, new_conflict, [decision]) is None


def test_missing_user_reference_or_out_of_scope_conflict_cannot_be_accepted():
    assert accepted_instruction(scope, conflict, [replace(decision, instruction_ref=" ")]) is None
    outside = replace(conflict, reader=C)
    assert accepted_instruction(scope, outside, [replace(decision, conflict=outside)]) is None


def test_additional_observation_of_same_assertion_preserves_existing_decision():
    more_evidence = replace(conflict, evidence_refs=("visible:new-observation",))
    assert accepted_instruction(scope, more_evidence, [decision]) == "message:12"


def test_concurrent_request_without_a_conflict_decision_has_no_matching_reference():
    assert accepted_instruction(scope, conflict, []) is None
    assert accepted_instruction(scope, replace(conflict, evidence_refs=()), [decision]) is None
