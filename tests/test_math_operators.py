from __future__ import annotations

import pytest

from respondent_lab.mechanisms.math_operators import (
    ALG_DISTRIBUTIVE_DROP,
    ALG_ILLEGAL_CANCEL,
    ALG_SIGN_MOVE,
    ALG_SQRT_SIGN_DROP,
    CALC_CHAIN_RULE_DROP,
)
from respondent_lab.schemas.items import Item


CASES = [
    (
        ALG_SIGN_MOVE,
        {"type": "numeric", "value": "7"},
        "numeric",
        [{"symbol": "equation", "value": "3*x - 5 = 16"}],
    ),
    (
        ALG_DISTRIBUTIVE_DROP,
        {"type": "formula", "value": "6*x + 8"},
        "formula",
        [{"symbol": "expression", "value": "2*(3*x + 4)"}],
    ),
    (
        ALG_ILLEGAL_CANCEL,
        {"type": "formula", "value": "x + 5/3"},
        "formula",
        [{"symbol": "expression", "value": "(3*x + 5)/3"}],
    ),
    (
        ALG_SQRT_SIGN_DROP,
        {"type": "answer_set", "value": ["-1", "5"]},
        "answer_set",
        [{"symbol": "equation", "value": "(x - 2)**2 = 9"}],
    ),
    (
        CALC_CHAIN_RULE_DROP,
        {"type": "formula", "value": "12*(3*x + 2)**3"},
        "formula",
        [{"symbol": "expression", "value": "(3*x + 2)**4"}],
    ),
]


@pytest.mark.parametrize("operator,correct,answer_type,givens", CASES)
def test_math_operator_positive_precondition_and_apply(
    payload_factory, operator, correct, answer_type, givens
) -> None:
    item = Item.model_validate(
        payload_factory(
            answer_type=answer_type,
            correct_answer=correct,
            givens=givens,
            allowed_operator_ids=[operator.operator_id],
        )
    )
    assert operator.preconditions(item.solution_trace, item) is True
    wrong_trace = operator.apply(item.solution_trace, item)
    report = operator.verify(wrong_trace, item)
    assert report.trace_executable is True
    assert report.matches_operator is True
    assert report.is_incorrect is True


@pytest.mark.parametrize("operator", [case[0] for case in CASES])
def test_math_operator_negative_precondition(payload_factory, operator) -> None:
    item = Item.model_validate(
        payload_factory(
            correct_answer={"type": "numeric", "value": "1"},
            givens=[{"symbol": "value", "value": "x"}],
            allowed_operator_ids=[operator.operator_id],
        )
    )
    assert operator.preconditions(item.solution_trace, item) is False
    with pytest.raises(ValueError):
        operator.apply(item.solution_trace, item)


@pytest.mark.parametrize(
    "operator,givens",
    [
        (
            ALG_DISTRIBUTIVE_DROP,
            [{"symbol": "equation", "value": r"\(\frac{3}{2}(x-4)+2=11\)"}],
        ),
        (
            ALG_DISTRIBUTIVE_DROP,
            [{"symbol": "equation", "value": r"\(3(x-2)^2+6=33\)"}],
        ),
        (
            ALG_ILLEGAL_CANCEL,
            [{"symbol": "expression", "value": r"\(\frac{4y+9}{4y+3}\)"}],
        ),
        (
            CALC_CHAIN_RULE_DROP,
            [{"symbol": "function", "value": r"\(y=\ln(4x^2+1)\)"}],
        ),
    ],
)
def test_math_operator_preconditions_scan_equation_sides_latex_and_symbols(
    payload_factory, operator, givens
) -> None:
    item = Item.model_validate(
        payload_factory(
            correct_answer={"type": "formula", "value": "x"},
            answer_type="formula",
            givens=givens,
            allowed_operator_ids=[operator.operator_id],
        )
    )

    assert operator.preconditions(item.solution_trace, item) is True


def test_sqrt_sign_drop_does_not_fire_on_zero_root(payload_factory) -> None:
    item = Item.model_validate(
        payload_factory(
            correct_answer={"type": "answer_set", "value": ["1"]},
            answer_type="answer_set",
            givens=[{"symbol": "equation", "value": r"\((x-1)^2=0\)"}],
            allowed_operator_ids=[ALG_SQRT_SIGN_DROP.operator_id],
        )
    )

    assert ALG_SQRT_SIGN_DROP.preconditions(item.solution_trace, item) is False
