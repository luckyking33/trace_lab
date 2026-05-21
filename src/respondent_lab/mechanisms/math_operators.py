"""Canonical MVP math error operators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sympy import Add, Pow, simplify, sqrt, symbols
from sympy.parsing.sympy_parser import parse_expr

from respondent_lab.mechanisms.base import ErrorOperator
from respondent_lab.schemas.items import Item
from respondent_lab.schemas.traces import SolutionTrace, TraceStep, WrongTrace
from respondent_lab.schemas.verification import VerificationReport

X = symbols("x")


def _allowed(item: Item, operator_id: str) -> bool:
    return item.subject == "math" and operator_id in item.allowed_operator_ids


def _strings_from_item(item: Item, trace: SolutionTrace) -> list[str]:
    values: list[str] = [item.question]
    for entry in [*item.givens, *item.constraints]:
        for value in entry.values():
            if isinstance(value, str):
                values.append(value)
    for step in trace.steps:
        values.append(step.expr)
        if step.result:
            values.append(step.result)
    return values


def _parse_sympy(text: str) -> Any:
    return parse_expr(text.replace("^", "**"), evaluate=False)


def _equation_strings(item: Item, trace: SolutionTrace) -> list[str]:
    return [text for text in _strings_from_item(item, trace) if "=" in text]


def _expression_strings(item: Item, trace: SolutionTrace) -> list[str]:
    return [text for text in _strings_from_item(item, trace) if "=" not in text]


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
    left_text, right_text = equation.split("=", 1)
    left = _parse_sympy(left_text)
    right = _parse_sympy(right_text)
    if right.has(X):
        return None
    coefficient = simplify(left.coeff(X))
    if coefficient == 0:
        return None
    constant = simplify(left - coefficient * X)
    if constant == 0 or constant.has(X):
        return None
    return simplify((right + constant) / coefficient)


def _distributive_drop_candidate(expression: str) -> Any | None:
    expr = _parse_sympy(expression)
    if not expr.is_Mul:
        return None
    add_factor = next((factor for factor in expr.args if isinstance(factor, Add)), None)
    if add_factor is None:
        return None
    multiplier = simplify(expr / add_factor)
    x_terms = [term for term in add_factor.args if term.has(X)]
    constants = [term for term in add_factor.args if not term.has(X)]
    if len(x_terms) != 1 or len(constants) != 1:
        return None
    return simplify(multiplier * x_terms[0] + constants[0])


def _illegal_cancel_candidate(expression: str) -> Any | None:
    expr = _parse_sympy(expression)
    if not expr.is_Mul:
        return None
    numerator = None
    denominator = None
    for factor in expr.args:
        if isinstance(factor, Pow) and factor.exp == -1:
            denominator = factor.base
        else:
            numerator = factor if numerator is None else numerator * factor
    if numerator is None or denominator is None or not isinstance(numerator, Add):
        return None
    terms = list(numerator.args)
    rewritten: list[Any] = []
    divided = False
    for term in terms:
        if not divided and term.has(X):
            rewritten.append(term / denominator)
            divided = True
        else:
            rewritten.append(term)
    if not divided:
        return None
    return simplify(sum(rewritten))


def _sqrt_sign_drop_candidate(equation: str) -> Any | None:
    left_text, right_text = equation.split("=", 1)
    left = _parse_sympy(left_text)
    right = _parse_sympy(right_text)
    if not isinstance(left, Pow) or left.exp != 2:
        return None
    base = left.base
    coefficient = simplify(base.coeff(X))
    if coefficient != 1:
        return None
    offset = simplify(-base.subs(X, 0))
    if right.has(X):
        return None
    return simplify(offset + sqrt(right))


def _chain_rule_drop_candidate(expression: str) -> Any | None:
    expr = _parse_sympy(expression)
    if not isinstance(expr, Pow):
        return None
    base = expr.base
    exponent = expr.exp
    if not base.has(X) or exponent.has(X):
        return None
    if simplify(base.diff(X)) == 1:
        return None
    return simplify(exponent * (base ** (exponent - 1)))


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
