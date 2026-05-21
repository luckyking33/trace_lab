from __future__ import annotations

from respondent_lab.schemas.items import AnswerObject
from respondent_lab.verifiers.formal_verifier import equivalent, is_incorrect, is_unique


def test_numeric_equivalence() -> None:
    assert equivalent(
        AnswerObject(type="numeric", value="1/3"),
        AnswerObject(type="numeric", value=0.3333333334),
    )


def test_symbolic_equivalence() -> None:
    assert equivalent(
        AnswerObject(type="formula", value="x + x"),
        AnswerObject(type="formula", value="2*x"),
    )


def test_answer_set_equivalence() -> None:
    assert equivalent(
        AnswerObject(type="answer_set", value=["2", "1"]),
        AnswerObject(type="answer_set", value=["1", "2"]),
    )


def test_unit_equivalence_with_pint() -> None:
    assert equivalent(
        AnswerObject(type="unit", value=100, unit="centimeter"),
        AnswerObject(type="unit", value=1, unit="meter"),
    )


def test_vector_equivalence() -> None:
    assert equivalent(
        AnswerObject(type="vector", value=["1", "2"]),
        AnswerObject(type="vector", value=[1.0, 2.0]),
    )


def test_incorrectness_and_uniqueness() -> None:
    correct = AnswerObject(type="numeric", value="7")
    candidate = AnswerObject(type="numeric", value="5")
    existing = [AnswerObject(type="numeric", value="4")]
    assert is_incorrect(candidate, correct)
    assert is_unique(candidate, correct, existing)
    assert not is_unique(candidate, correct, [candidate])
