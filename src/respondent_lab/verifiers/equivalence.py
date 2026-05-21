"""Formal answer equivalence dispatchers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from respondent_lab.schemas.items import AnswerObject
from respondent_lab.verifiers.numeric_verifier import numeric_equivalent
from respondent_lab.verifiers.symbolic_verifier import symbolic_equivalent
from respondent_lab.verifiers.unit_verifier import unit_equivalent


def _answer(value: AnswerObject | dict[str, Any]) -> AnswerObject:
    if isinstance(value, AnswerObject):
        return value
    if isinstance(value, dict):
        return AnswerObject.model_validate(value)
    raise ValueError(f"expected AnswerObject or dict, got {type(value).__name__}")


def _element_equivalent(a: Any, b: Any, *, tolerance: float) -> bool:
    if isinstance(a, dict) or isinstance(b, dict):
        try:
            return equivalent(_answer(a), _answer(b), tolerance=tolerance)
        except Exception:
            return False
    try:
        return numeric_equivalent(a, b, tolerance=tolerance)
    except Exception:
        pass
    try:
        return symbolic_equivalent(a, b)
    except Exception:
        pass
    return str(a).strip() == str(b).strip()


def _answer_set_equivalent(a: AnswerObject, b: AnswerObject, *, tolerance: float) -> bool:
    values_a = list(a.value)
    values_b = list(b.value)
    if len(values_a) != len(values_b):
        return False
    used: set[int] = set()
    for item_a in values_a:
        match_idx = None
        for idx, item_b in enumerate(values_b):
            if idx in used:
                continue
            if _element_equivalent(item_a, item_b, tolerance=tolerance):
                match_idx = idx
                break
        if match_idx is None:
            return False
        used.add(match_idx)
    return True


def _vector_equivalent(a: AnswerObject, b: AnswerObject, *, tolerance: float) -> bool:
    values_a = list(a.value)
    values_b = list(b.value)
    if len(values_a) != len(values_b):
        return False
    return all(
        numeric_equivalent(component_a, component_b, tolerance=tolerance)
        for component_a, component_b in zip(values_a, values_b)
    )


def equivalent(a: AnswerObject, b: AnswerObject, *, tolerance: float = 1e-6) -> bool:
    """Return whether two formal answer objects are equivalent."""

    a = _answer(a)
    b = _answer(b)
    if a.type == b.type == "numeric":
        return numeric_equivalent(a, b, tolerance=tolerance)
    if a.type == b.type == "formula":
        return symbolic_equivalent(a, b)
    if a.type == b.type == "unit":
        return unit_equivalent(a, b, tolerance=tolerance)
    if a.type == b.type == "vector":
        return _vector_equivalent(a, b, tolerance=tolerance)
    if a.type == b.type == "answer_set":
        return _answer_set_equivalent(a, b, tolerance=tolerance)
    if a.type == b.type == "conceptual":
        return str(a.value).strip().casefold() == str(b.value).strip().casefold()

    if {a.type, b.type} <= {"numeric", "formula"}:
        try:
            return numeric_equivalent(a, b, tolerance=tolerance)
        except Exception:
            return symbolic_equivalent(a, b)

    return False


def is_incorrect(candidate: AnswerObject, correct: AnswerObject) -> bool:
    return not equivalent(candidate, correct)


def is_unique(
    candidate: AnswerObject, correct: AnswerObject, existing: Sequence[AnswerObject]
) -> bool:
    if equivalent(candidate, correct):
        return False
    return not any(equivalent(candidate, other) for other in existing)
