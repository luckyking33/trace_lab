"""Symbolic equivalence checks backed by SymPy."""

from __future__ import annotations

from typing import Any

from sympy import simplify, sympify

from respondent_lab.schemas.items import AnswerObject


def symbolic_expr(value: AnswerObject | Any) -> Any:
    raw = value.value if isinstance(value, AnswerObject) else value
    if isinstance(raw, (int, float)):
        return sympify(raw)
    if isinstance(raw, str):
        try:
            return sympify(raw)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"unparseable symbolic answer: {raw}") from exc
    raise ValueError(f"unsupported symbolic answer: {raw!r}")


def symbolic_equivalent(a: AnswerObject | Any, b: AnswerObject | Any) -> bool:
    expr_a = symbolic_expr(a)
    expr_b = symbolic_expr(b)
    return simplify(expr_a - expr_b) == 0
