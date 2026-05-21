"""Numeric answer equivalence with explicit parse failures."""

from __future__ import annotations

from typing import Any

from sympy import N, sympify

from respondent_lab.schemas.items import AnswerObject


def numeric_value(value: AnswerObject | Any) -> float:
    raw = value.value if isinstance(value, AnswerObject) else value
    if isinstance(raw, bool):
        raise ValueError("boolean is not a numeric answer")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(N(sympify(raw)))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"unparseable numeric answer: {raw}") from exc
    raise ValueError(f"unsupported numeric answer: {raw!r}")


def numeric_equivalent(a: AnswerObject | Any, b: AnswerObject | Any, *, tolerance: float) -> bool:
    return abs(numeric_value(a) - numeric_value(b)) <= tolerance
