"""Structured MVP physics error operators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from respondent_lab.mechanisms.base import ErrorOperator
from respondent_lab.schemas.items import Item
from respondent_lab.schemas.traces import SolutionTrace, TraceStep, WrongTrace
from respondent_lab.schemas.verification import VerificationReport


def _allowed(item: Item, operator_id: str) -> bool:
    return item.subject == "physics" and operator_id in item.allowed_operator_ids


def _all_structured(item: Item) -> list[dict[str, Any]]:
    return [*item.givens, *item.constraints]


def _has_marker(item: Item, *markers: str) -> bool:
    marker_set = {marker.lower() for marker in markers}
    for entry in _all_structured(item):
        text = " ".join(str(value).lower() for value in entry.values())
        keys = {str(key).lower() for key in entry}
        if keys & marker_set or any(marker in text for marker in marker_set):
            return True
    return any(marker in item.question.lower() for marker in marker_set)


def _answer_payload(item: Item, value: Any, unit: str | None = None) -> dict[str, Any]:
    if item.answer_type == "unit" or unit is not None:
        return {"type": "unit", "value": value, "unit": unit or ""}
    if item.answer_type == "vector":
        return {"type": "vector", "value": value}
    if item.answer_type == "numeric":
        return {"type": "numeric", "value": str(value)}
    return {"type": item.answer_type, "value": value}


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
        metadata={"source": "structured_mvp_physics_operator"},
    )


def _correct_numeric(item: Item) -> float | None:
    try:
        return float(item.correct_answer.value)
    except Exception:
        return None


def _unit_conversion_candidate(item: Item) -> tuple[Any, str | None] | None:
    for entry in item.givens:
        if {"value", "unit", "target_unit"} <= set(entry):
            return entry["value"], entry.get("target_unit")
        if entry.get("operator_pattern") == "unit_conversion":
            return entry.get("wrong_value", entry.get("value")), entry.get("target_unit", entry.get("unit"))
    return None


def _vector_sign_candidate(item: Item) -> Any | None:
    for entry in _all_structured(item):
        if "wrong_signed_value" in entry:
            return entry["wrong_signed_value"]
    correct = _correct_numeric(item)
    if correct is not None:
        return -correct
    return None


def _scalar_vector_candidate(item: Item) -> Any | None:
    for entry in item.givens:
        if {"vx", "vy"} <= set(entry):
            return float(entry["vx"]) + float(entry["vy"])
        if "components" in entry and isinstance(entry["components"], list):
            return sum(float(value) for value in entry["components"])
    return None


def _formula_domain_candidate(item: Item) -> Any | None:
    for entry in _all_structured(item):
        if "misused_formula_answer" in entry:
            return entry["misused_formula_answer"]
        if entry.get("condition_satisfied") is False and "formula_answer" in entry:
            return entry["formula_answer"]
    return None


def _celsius_kelvin_candidate(item: Item) -> Any | None:
    for entry in item.givens:
        if "temperature_c" in entry:
            return entry["temperature_c"]
        if str(entry.get("unit", "")).lower() in {"c", "celsius", "degc"} and "value" in entry:
            return entry["value"]
    return None


@dataclass(frozen=True)
class _PhysicsOperator:
    operator_id: str
    domain: str
    description: str

    subject: str = "physics"

    def _candidate(self, item: Item) -> tuple[str, dict[str, Any]] | None:
        if self.operator_id == "PHY_UNIT_CONVERSION":
            found = _unit_conversion_candidate(item)
            if found is not None:
                value, unit = found
                return "unit conversion omitted", _answer_payload(item, value, unit)
        if self.operator_id == "PHY_VECTOR_SIGN":
            if _has_marker(item, "direction", "sign_convention", "vector_sign"):
                candidate = _vector_sign_candidate(item)
                if candidate is not None:
                    return "vector sign convention reversed", _answer_payload(item, candidate)
        if self.operator_id == "PHY_SCALAR_VECTOR_CONFUSION":
            candidate = _scalar_vector_candidate(item)
            if candidate is not None:
                return "vector magnitude treated as scalar sum", _answer_payload(item, candidate)
        if self.operator_id == "PHY_FORMULA_DOMAIN_MISUSE":
            candidate = _formula_domain_candidate(item)
            if candidate is not None:
                return "formula used outside its domain", _answer_payload(item, candidate)
        if self.operator_id == "PHY_CELSIUS_KELVIN_CONFUSION":
            candidate = _celsius_kelvin_candidate(item)
            if candidate is not None:
                return "Celsius magnitude used as Kelvin", _answer_payload(item, candidate, "kelvin")
        return None

    def preconditions(self, trace: SolutionTrace, item: Item) -> bool:
        return _allowed(item, self.operator_id) and self._candidate(item) is not None

    def apply(self, trace: SolutionTrace, item: Item) -> WrongTrace:
        found = self._candidate(item)
        if not _allowed(item, self.operator_id) or found is None:
            raise ValueError(f"Preconditions not met for {self.operator_id}")
        expr, payload = found
        return _wrong_trace(self.operator_id, item, trace, expr, f"apply {self.operator_id}", payload)

    def verify(self, wrong_trace: WrongTrace, item: Item) -> VerificationReport:
        from respondent_lab.mechanisms.trace_executor import check_trace_executable

        return check_trace_executable(wrong_trace, item, self)


PHY_UNIT_CONVERSION = _PhysicsOperator(
    operator_id="PHY_UNIT_CONVERSION",
    domain="units",
    description="Treat a quantity as already converted to the target unit.",
)
PHY_VECTOR_SIGN = _PhysicsOperator(
    operator_id="PHY_VECTOR_SIGN",
    domain="kinematics",
    description="Reverse the sign implied by the direction convention.",
)
PHY_SCALAR_VECTOR_CONFUSION = _PhysicsOperator(
    operator_id="PHY_SCALAR_VECTOR_CONFUSION",
    domain="vectors",
    description="Use scalar addition where vector magnitude is required.",
)
PHY_FORMULA_DOMAIN_MISUSE = _PhysicsOperator(
    operator_id="PHY_FORMULA_DOMAIN_MISUSE",
    domain="mechanics",
    description="Use a formula outside its stated applicability conditions.",
)
PHY_CELSIUS_KELVIN_CONFUSION = _PhysicsOperator(
    operator_id="PHY_CELSIUS_KELVIN_CONFUSION",
    domain="thermal",
    description="Use Celsius magnitude directly in a Kelvin formula.",
)

PHYSICS_OPERATORS: list[ErrorOperator] = [
    PHY_UNIT_CONVERSION,
    PHY_VECTOR_SIGN,
    PHY_SCALAR_VECTOR_CONFUSION,
    PHY_FORMULA_DOMAIN_MISUSE,
    PHY_CELSIUS_KELVIN_CONFUSION,
]
