"""Canonical MVP math error operators."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sympy import Add, Dummy, E, Pow, expand, preorder_traversal, simplify, sqrt, symbols
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from respondent_lab.io.normalization import strip_latex_wrappers
from respondent_lab.mechanisms.base import ErrorOperator
from respondent_lab.schemas.items import Item
from respondent_lab.schemas.traces import SolutionTrace, TraceStep, WrongTrace
from respondent_lab.schemas.verification import VerificationReport

X = symbols("x")
TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)
INLINE_MATH_RE = re.compile(r"\\\((.*?)\\\)|\\\[(.*?)\\\]|\$(.*?)\$")


def _allowed(item: Item, operator_id: str) -> bool:
    return item.subject == "math" and operator_id in item.allowed_operator_ids


def _normalize_math_text(text: str) -> str:
    normalized = strip_latex_wrappers(str(text))
    normalized = normalized.replace(r"\ln", "log")
    normalized = normalized.replace(r"\sin", "sin")
    normalized = normalized.replace(r"\cos", "cos")
    normalized = normalized.replace(r"\tan", "tan")
    normalized = normalized.replace(r"\exp", "exp")
    normalized = normalized.replace("\\", "")
    normalized = normalized.replace("ln(", "log(")
    normalized = re.sub(r"\be\*\*", "E**", normalized)
    normalized = normalized.strip().rstrip(".")
    return normalized


def _math_segments(text: str) -> list[str]:
    segments: list[str] = []
    for match in INLINE_MATH_RE.finditer(str(text)):
        segment = next(group for group in match.groups() if group is not None)
        segments.append(segment)
    segments.append(str(text))
    return segments


def _strings_from_item(item: Item, trace: SolutionTrace) -> list[str]:
    raw_values: list[str] = [item.question]
    for entry in [*item.givens, *item.constraints]:
        for value in entry.values():
            if isinstance(value, str):
                raw_values.append(value)
    for step in trace.steps:
        raw_values.append(step.expr)
        if step.result:
            raw_values.append(step.result)

    values: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        for segment in _math_segments(raw_value):
            normalized = _normalize_math_text(segment)
            if normalized and normalized not in seen:
                seen.add(normalized)
                values.append(normalized)
    return values


def _parse_sympy(text: str, *, evaluate: bool = True) -> Any:
    return parse_expr(
        _normalize_math_text(text),
        local_dict={"E": E},
        transformations=TRANSFORMATIONS,
        evaluate=evaluate,
    )


def _equation_pairs(equation: str) -> list[tuple[str, str]]:
    parts = [part.strip() for part in equation.split("=")]
    return [(left, right) for left, right in zip(parts, parts[1:]) if left and right]


def _equation_strings(item: Item, trace: SolutionTrace) -> list[str]:
    return [text for text in _strings_from_item(item, trace) if "=" in text]


def _expression_strings(item: Item, trace: SolutionTrace) -> list[str]:
    expressions: list[str] = []
    seen: set[str] = set()
    for text in _strings_from_item(item, trace):
        candidates = [text]
        if "=" in text:
            candidates = []
            for left, right in _equation_pairs(text):
                candidates.extend([left, right])
        for candidate in candidates:
            candidate = candidate.strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                expressions.append(candidate)
    return expressions


def _symbols_in(expr: Any) -> list[Any]:
    return sorted(expr.free_symbols, key=lambda symbol: str(symbol))


def _primary_symbol(expr: Any) -> Any | None:
    free_symbols = _symbols_in(expr)
    if X in free_symbols:
        return X
    return free_symbols[0] if free_symbols else None


def _subexpressions(expr: Any) -> list[Any]:
    return list(preorder_traversal(expr))


def _answer_payload(item: Item, value: Any) -> dict[str, Any]:
    text = str(simplify(value))
    if item.answer_type == "answer_set":
        return {"type": "answer_set", "value": [text]}
    if item.answer_type == "numeric":
        return {"type": "numeric", "value": text}
    return {"type": "formula", "value": text}


def _wrong_trace(
    operator_id: str,
    item: Item,
    trace: SolutionTrace,
    expr: str,
    operation: str,
    answer_payload: dict[str, Any],
) -> WrongTrace:
    first = trace.steps[0].model_copy(deep=True)
    divergence_id = first.step_id + 1
    divergence = TraceStep(
        step_id=divergence_id,
        expr=expr,
        operation=operation,
        result=str(answer_payload["value"]),
        operator_id=operator_id,
        is_divergence=True,
        metadata={"operator_id": operator_id},
    )
    final = TraceStep(
        step_id=divergence_id + 1,
        expr=expr,
        operation="extract wrong answer",
        result=str(answer_payload["value"]),
        metadata={"derived_answer": answer_payload},
    )
    return WrongTrace(
        item_id=item.item_id,
        operator_id=operator_id,
        steps=[first, divergence, final],
        candidate_answer=answer_payload,
        metadata={"source": "canonical_mvp_math_operator"},
    )


def _linear_sign_move_candidate(equation: str) -> Any | None:
    for left_text, right_text in _equation_pairs(equation):
        left = _parse_sympy(left_text)
        right = _parse_sympy(right_text)
        symbol = _primary_symbol(left - right)
        if symbol is None:
            continue
        coefficient_left = simplify(left.coeff(symbol))
        coefficient_right = simplify(right.coeff(symbol))
        constant_left = simplify(left - coefficient_left * symbol)
        constant_right = simplify(right - coefficient_right * symbol)

        if coefficient_right == 0 and coefficient_left != 0 and constant_left != 0:
            return simplify((right + constant_left) / coefficient_left)

        if coefficient_right != 0 and coefficient_left != 0:
            denominator = simplify(coefficient_left + coefficient_right)
            if denominator != 0:
                return simplify((constant_right - constant_left) / denominator)

        if any(
            part.has(symbol) and part.is_Add
            for part in [left, right]
        ):
            return simplify(left + right)
    return None


def _distributive_drop_candidate(expression: str) -> Any | None:
    expr = _parse_sympy(expression, evaluate=False)
    for subexpr in _subexpressions(expr):
        if not getattr(subexpr, "is_Mul", False):
            continue
        add_factor = next((factor for factor in subexpr.args if isinstance(factor, Add)), None)
        power_add_factor = next(
            (
                factor
                for factor in subexpr.args
                if isinstance(factor, Pow)
                and isinstance(factor.base, Add)
                and factor.exp.is_integer
                and factor.exp > 1
            ),
            None,
        )
        factor_to_drop = add_factor or power_add_factor
        if factor_to_drop is None:
            continue

        if add_factor is not None:
            multiplier = simplify(subexpr / add_factor)
            add_terms = add_factor.as_ordered_terms()
        else:
            multiplier = simplify(subexpr / power_add_factor)
            add_terms = expand(power_add_factor).as_ordered_terms()

        first_symbolic_index = next(
            (idx for idx, term in enumerate(add_terms) if term.free_symbols),
            None,
        )
        if first_symbolic_index is None or len(add_terms) < 2:
            continue
        rewritten_terms = list(add_terms)
        rewritten_terms[first_symbolic_index] = multiplier * rewritten_terms[first_symbolic_index]
        wrong_subexpr = simplify(sum(rewritten_terms))
        if subexpr == expr:
            return wrong_subexpr
        return simplify(expr.xreplace({subexpr: wrong_subexpr}))
    return None


def _illegal_cancel_candidate(expression: str) -> Any | None:
    expr = _parse_sympy(expression, evaluate=False)
    for subexpr in _subexpressions(expr):
        if not getattr(subexpr, "is_Mul", False):
            continue
        numerator = None
        denominator = None
        for factor in subexpr.args:
            if isinstance(factor, Pow) and factor.exp == -1:
                denominator = factor.base
            else:
                numerator = factor if numerator is None else numerator * factor
        if numerator is None or denominator is None or not isinstance(numerator, Add):
            continue
        numerator_symbols = set(numerator.free_symbols)
        denominator_symbols = set(denominator.free_symbols)
        if not numerator_symbols:
            continue
        terms = list(numerator.args)
        rewritten: list[Any] = []
        divided = False
        for term in terms:
            if not divided and (
                term.free_symbols & denominator_symbols
                or (not denominator_symbols and term.free_symbols)
            ):
                rewritten.append(term / denominator)
                divided = True
            else:
                rewritten.append(term)
        if not divided:
            continue
        wrong_subexpr = simplify(sum(rewritten))
        if subexpr == expr:
            return wrong_subexpr
        return simplify(expr.xreplace({subexpr: wrong_subexpr}))
    return None


def _sqrt_sign_drop_candidate(equation: str) -> Any | None:
    for left_text, right_text in _equation_pairs(equation):
        left = _parse_sympy(left_text)
        right = _parse_sympy(right_text)
        if not isinstance(left, Pow) or left.exp != 2:
            continue
        symbol = _primary_symbol(left)
        if symbol is None or right.has(symbol) or simplify(right) == 0:
            continue
        base = left.base
        coefficient = simplify(base.coeff(symbol))
        if coefficient == 0:
            continue
        offset = simplify(-base.subs(symbol, 0) / coefficient)
        return simplify(offset + sqrt(right) / coefficient)
    return None


def _chain_rule_drop_candidate(expression: str) -> Any | None:
    expr = _parse_sympy(expression)
    for subexpr in _subexpressions(expr):
        if not subexpr.has(X):
            continue
        if isinstance(subexpr, Pow):
            base = subexpr.base
            exponent = subexpr.exp
            if base.has(X) and not exponent.has(X) and simplify(base.diff(X)) not in (0, 1):
                return simplify(exponent * (base ** (exponent - 1)))
            if exponent.has(X) and simplify(exponent.diff(X)) not in (0, 1):
                return simplify(subexpr)
        if getattr(subexpr, "is_Function", False) and subexpr.args:
            inner = subexpr.args[0]
            if inner.has(X) and simplify(inner.diff(X)) not in (0, 1):
                placeholder = Dummy("inner")
                outer = subexpr.xreplace({inner: placeholder})
                return simplify(outer.diff(placeholder).subs(placeholder, inner))
    return None


@dataclass(frozen=True)
class _MathOperator:
    operator_id: str
    domain: str
    description: str

    subject: str = "math"

    def _candidate(self, trace: SolutionTrace, item: Item) -> tuple[str, Any] | None:
        if self.operator_id == "ALG_SIGN_MOVE":
            for equation in _equation_strings(item, trace):
                try:
                    candidate = _linear_sign_move_candidate(equation)
                except Exception:
                    candidate = None
                if candidate is not None:
                    return equation, candidate
        if self.operator_id == "ALG_DISTRIBUTIVE_DROP":
            for expression in _expression_strings(item, trace):
                try:
                    candidate = _distributive_drop_candidate(expression)
                except Exception:
                    candidate = None
                if candidate is not None:
                    return expression, candidate
        if self.operator_id == "ALG_ILLEGAL_CANCEL":
            for expression in _expression_strings(item, trace):
                try:
                    candidate = _illegal_cancel_candidate(expression)
                except Exception:
                    candidate = None
                if candidate is not None:
                    return expression, candidate
        if self.operator_id == "ALG_SQRT_SIGN_DROP":
            for equation in _equation_strings(item, trace):
                try:
                    candidate = _sqrt_sign_drop_candidate(equation)
                except Exception:
                    candidate = None
                if candidate is not None:
                    return equation, candidate
        if self.operator_id == "CALC_CHAIN_RULE_DROP":
            for expression in _expression_strings(item, trace):
                try:
                    candidate = _chain_rule_drop_candidate(expression)
                except Exception:
                    candidate = None
                if candidate is not None:
                    return expression, candidate
        return None

    def preconditions(self, trace: SolutionTrace, item: Item) -> bool:
        return _allowed(item, self.operator_id) and self._candidate(trace, item) is not None

    def apply(self, trace: SolutionTrace, item: Item) -> WrongTrace:
        found = self._candidate(trace, item)
        if not _allowed(item, self.operator_id) or found is None:
            raise ValueError(f"Preconditions not met for {self.operator_id}")
        source_expr, candidate = found
        payload = _answer_payload(item, candidate)
        return _wrong_trace(
            self.operator_id,
            item,
            trace,
            str(candidate),
            f"apply {self.operator_id} to {source_expr}",
            payload,
        )

    def verify(self, wrong_trace: WrongTrace, item: Item) -> VerificationReport:
        from respondent_lab.mechanisms.trace_executor import check_trace_executable

        return check_trace_executable(wrong_trace, item, self)


ALG_SIGN_MOVE = _MathOperator(
    operator_id="ALG_SIGN_MOVE",
    domain="algebra",
    description="Move an additive term across an equals sign without changing sign.",
)
ALG_DISTRIBUTIVE_DROP = _MathOperator(
    operator_id="ALG_DISTRIBUTIVE_DROP",
    domain="algebra",
    description="Distribute multiplication to the first term but not the second.",
)
ALG_ILLEGAL_CANCEL = _MathOperator(
    operator_id="ALG_ILLEGAL_CANCEL",
    domain="algebra",
    description="Cancel a factor across addition.",
)
ALG_SQRT_SIGN_DROP = _MathOperator(
    operator_id="ALG_SQRT_SIGN_DROP",
    domain="algebra",
    description="Drop the negative branch after taking a square root.",
)
CALC_CHAIN_RULE_DROP = _MathOperator(
    operator_id="CALC_CHAIN_RULE_DROP",
    domain="calculus",
    description="Differentiate a composite expression while omitting the inner derivative.",
)

MATH_OPERATORS: list[ErrorOperator] = [
    ALG_SIGN_MOVE,
    ALG_DISTRIBUTIVE_DROP,
    ALG_ILLEGAL_CANCEL,
    ALG_SQRT_SIGN_DROP,
    CALC_CHAIN_RULE_DROP,
]
