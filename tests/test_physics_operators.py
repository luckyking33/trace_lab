from __future__ import annotations

import pytest

from respondent_lab.mechanisms.physics_operators import (
    PHY_CELSIUS_KELVIN_CONFUSION,
    PHY_FORMULA_DOMAIN_MISUSE,
    PHY_SCALAR_VECTOR_CONFUSION,
    PHY_UNIT_CONVERSION,
    PHY_VECTOR_SIGN,
)
from respondent_lab.schemas.items import Item


CASES = [
    (
        PHY_UNIT_CONVERSION,
        "unit",
        {"type": "unit", "value": 0.3, "unit": "meter"},
        [{"value": 30, "unit": "centimeter", "target_unit": "meter"}],
        [],
        "Length conversion.",
    ),
    (
        PHY_VECTOR_SIGN,
        "numeric",
        {"type": "numeric", "value": "-5"},
        [{"sign_convention": "right positive", "wrong_signed_value": "5"}],
        [],
        "A direction convention is stated.",
    ),
    (
        PHY_SCALAR_VECTOR_CONFUSION,
        "numeric",
        {"type": "numeric", "value": "5"},
        [{"vx": 3, "vy": 4}],
        [],
        "Find the vector magnitude.",
    ),
    (
        PHY_FORMULA_DOMAIN_MISUSE,
        "numeric",
        {"type": "numeric", "value": "10"},
        [],
        [{"condition_satisfied": False, "formula_answer": "6"}],
        "Formula domain test.",
    ),
    (
        PHY_CELSIUS_KELVIN_CONFUSION,
        "unit",
        {"type": "unit", "value": 298.15, "unit": "kelvin"},
        [{"temperature_c": 25}],
        [],
        "Thermal calculation.",
    ),
]


@pytest.mark.parametrize("operator,answer_type,correct,givens,constraints,question", CASES)
def test_physics_operator_positive_precondition_and_apply(
    payload_factory, operator, answer_type, correct, givens, constraints, question
) -> None:
    item = Item.model_validate(
        payload_factory(
            subject="physics",
            domain=operator.domain,
            answer_type=answer_type,
            correct_answer=correct,
            givens=givens,
            constraints=constraints,
            allowed_operator_ids=[operator.operator_id],
            question=question,
        )
    )
    assert operator.preconditions(item.solution_trace, item) is True
    wrong_trace = operator.apply(item.solution_trace, item)
    report = operator.verify(wrong_trace, item)
    assert report.trace_executable is True
    assert report.matches_operator is True
    assert report.is_incorrect is True


@pytest.mark.parametrize("operator", [case[0] for case in CASES])
def test_physics_operator_negative_precondition(payload_factory, operator) -> None:
    item = Item.model_validate(
        payload_factory(
            subject="physics",
            domain=operator.domain,
            correct_answer={"type": "numeric", "value": "1"},
            givens=[],
            constraints=[],
            allowed_operator_ids=[operator.operator_id],
        )
    )
    assert operator.preconditions(item.solution_trace, item) is False
    with pytest.raises(ValueError):
        operator.apply(item.solution_trace, item)
