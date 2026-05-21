from __future__ import annotations

from respondent_lab.mechanisms.math_operators import ALG_SIGN_MOVE, ALG_SQRT_SIGN_DROP
from respondent_lab.mechanisms.trace_executor import check_trace_executable, execute_wrong_trace
from respondent_lab.schemas.items import Item


def test_unique_divergence_pass(payload_factory) -> None:
    item = Item.model_validate(payload_factory())
    wrong_trace = ALG_SIGN_MOVE.apply(item.solution_trace, item)
    answer = execute_wrong_trace(wrong_trace, item)
    report = check_trace_executable(wrong_trace, item, ALG_SIGN_MOVE)
    assert answer.value == "11/3"
    assert report.trace_executable is True
    assert report.divergence_step == 2


def test_zero_divergence_fails(payload_factory) -> None:
    item = Item.model_validate(payload_factory())
    wrong_trace = ALG_SIGN_MOVE.apply(item.solution_trace, item)
    for step in wrong_trace.steps:
        step.is_divergence = False
    report = check_trace_executable(wrong_trace, item, ALG_SIGN_MOVE)
    assert report.trace_executable is False
    assert "expected exactly one divergence" in report.notes[0]


def test_multiple_divergence_fails(payload_factory) -> None:
    item = Item.model_validate(payload_factory())
    wrong_trace = ALG_SIGN_MOVE.apply(item.solution_trace, item)
    wrong_trace.steps[-1].is_divergence = True
    wrong_trace.steps[-1].operator_id = ALG_SIGN_MOVE.operator_id
    report = check_trace_executable(wrong_trace, item, ALG_SIGN_MOVE)
    assert report.trace_executable is False
    assert "found 2" in report.notes[0]


def test_operator_mismatch_fails(payload_factory) -> None:
    item = Item.model_validate(payload_factory())
    wrong_trace = ALG_SIGN_MOVE.apply(item.solution_trace, item)
    report = check_trace_executable(wrong_trace, item, ALG_SQRT_SIGN_DROP)
    assert report.matches_operator is False
    assert report.trace_executable is False
