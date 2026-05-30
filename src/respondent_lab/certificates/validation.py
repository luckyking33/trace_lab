"""Deterministic validation for extracted math certificates."""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from sympy import N, simplify, sympify
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from respondent_lab.io.normalization import (
    normalize_answer_object,
    normalize_item_record,
    normalize_trace_steps,
    strip_latex_wrappers,
)
from respondent_lab.mechanisms.operator_registry import get_operator, register_default_operators
from respondent_lab.schemas.items import Item
from respondent_lab.schemas.traces import WrongTrace


SUPPORTED_ANSWER_TYPES = {"numeric", "formula", "answer_set"}
TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)


def _value_present(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _string_key(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ",".join(_string_key(item) for item in value) + "]"
    return strip_latex_wrappers(str(value)).replace(" ", "")


def _parse_sympy(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("boolean is not a math answer")
    if isinstance(value, (int, float)):
        return sympify(value)
    text = strip_latex_wrappers(str(value))
    return parse_expr(text, transformations=TRANSFORMATIONS, evaluate=True)


def _scalar_equivalent(left: Any, right: Any, *, tolerance: float = 1e-6) -> tuple[bool, bool]:
    try:
        left_expr = _parse_sympy(left)
        right_expr = _parse_sympy(right)
        delta = simplify(left_expr - right_expr)
        if delta == 0:
            return True, False
        try:
            return abs(float(N(delta))) <= tolerance, False
        except Exception:
            return False, False
    except Exception:
        return _string_key(left) == _string_key(right), True


def _canonical_set(values: Any) -> tuple[list[str], bool]:
    if not isinstance(values, list):
        values = [values]
    parse_failure = False
    canonical: list[str] = []
    for value in values:
        try:
            canonical.append(str(simplify(_parse_sympy(value))))
        except Exception:
            canonical.append(_string_key(value))
            parse_failure = True
    return sorted(canonical), parse_failure


def answer_equivalent(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, bool]:
    """Return equivalence and whether parsing fell back to strings."""

    left = normalize_answer_object(left)
    right = normalize_answer_object(right)
    left_type = left.get("type")
    right_type = right.get("type")

    if left_type == right_type == "answer_set":
        left_values, left_failed = _canonical_set(left.get("value"))
        right_values, right_failed = _canonical_set(right.get("value"))
        return left_values == right_values, left_failed or right_failed

    if {left_type, right_type} <= {"numeric", "formula"}:
        return _scalar_equivalent(left.get("value"), right.get("value"))

    return _string_key(left.get("value")) == _string_key(right.get("value")), True


def _coerce_answer(raw: Any, answer_type: str) -> dict[str, Any]:
    if isinstance(raw, dict) and "type" in raw and "value" in raw:
        return normalize_answer_object(raw)
    value = raw
    if answer_type == "answer_set" and not isinstance(value, list):
        value = [value]
    return normalize_answer_object({"type": answer_type, "value": value})


def _extract_derived_answer(
    steps: list[dict[str, Any]], candidate_answer: dict[str, Any]
) -> dict[str, Any] | None:
    answer_type = str(candidate_answer.get("type") or "formula")
    for step in reversed(steps):
        metadata = step.get("metadata") or {}
        if "derived_answer" in metadata:
            return _coerce_answer(metadata["derived_answer"], answer_type)
        if "answer" in metadata:
            return _coerce_answer(metadata["answer"], answer_type)
        if _value_present(step.get("result")):
            return _coerce_answer(step.get("result"), answer_type)
    return None


def _validate_with_formal_verifier(
    record: dict[str, Any], certificate: dict[str, Any], operator_id: str
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        register_default_operators()
        item = Item.model_validate(record)
        operator = get_operator(operator_id)
        wrong_trace = WrongTrace(
            item_id=str(record.get("item_id") or ""),
            operator_id=operator_id,
            steps=certificate.get("wrong_solution_trace") or [],
            candidate_answer=certificate.get("candidate_answer"),
        )
        report = operator.verify(wrong_trace, item)
        return report.model_dump(), None
    except Exception as exc:  # noqa: BLE001 - validation reports errors structurally.
        return None, str(exc)


def validate_certificate(record: dict[str, Any], certificate: dict[str, Any]) -> dict[str, Any]:
    """Validate a normalized certificate against its source item."""

    normalized_record = normalize_item_record(record)
    normalized_certificate = copy.deepcopy(certificate)
    if isinstance(normalized_certificate.get("candidate_answer"), dict):
        normalized_certificate["candidate_answer"] = normalize_answer_object(
            normalized_certificate["candidate_answer"]
        )
    normalized_certificate["wrong_solution_trace"] = normalize_trace_steps(
        normalized_certificate.get("wrong_solution_trace") or []
    )

    candidate_answer = normalized_certificate.get("candidate_answer") or {}
    wrong_trace = normalized_certificate.get("wrong_solution_trace") or []
    applied_operator_ids = [
        str(operator_id)
        for operator_id in normalized_certificate.get("applied_operator_ids") or []
        if operator_id
    ]

    notes: list[str] = []
    has_candidate_answer = bool(candidate_answer) and _value_present(candidate_answer.get("value"))
    has_wrong_trace = bool(wrong_trace)
    candidate_answer_type_supported = candidate_answer.get("type") in SUPPORTED_ANSWER_TYPES
    single_operator_certificate = len(applied_operator_ids) == 1
    composite_certificate = len(applied_operator_ids) > 1
    composite_deferred = composite_certificate
    if composite_deferred:
        notes.append("composite certificate deferred in v0")
    if not candidate_answer_type_supported:
        notes.append(f"unsupported answer type: {candidate_answer.get('type')}")

    divergence_steps = [step for step in wrong_trace if step.get("is_divergence")]
    divergence_operator_ids = [step.get("operator_id") for step in divergence_steps if step.get("operator_id")]
    divergence_step_count = len(divergence_steps)

    if single_operator_certificate:
        operator_match = divergence_step_count == 1 and divergence_operator_ids == applied_operator_ids
    elif composite_certificate:
        operator_match = Counter(divergence_operator_ids) == Counter(applied_operator_ids)
    else:
        operator_match = False
        notes.append("missing applied operator id")

    derived_answer = _extract_derived_answer(wrong_trace, candidate_answer) if has_candidate_answer else None
    derived_answer_present = derived_answer is not None and _value_present(derived_answer.get("value"))

    parse_failure = False
    answer_match = False
    if has_candidate_answer and derived_answer_present:
        answer_match, answer_parse_failure = answer_equivalent(candidate_answer, derived_answer)
        parse_failure = parse_failure or answer_parse_failure
    elif has_candidate_answer:
        notes.append("derived answer not found")

    incorrectness = False
    unique_vs_correct = False
    if has_candidate_answer and isinstance(normalized_record.get("correct_answer"), dict):
        equivalent_to_correct, correct_parse_failure = answer_equivalent(
            candidate_answer, normalized_record["correct_answer"]
        )
        parse_failure = parse_failure or correct_parse_failure
        incorrectness = not equivalent_to_correct
        unique_vs_correct = incorrectness

    formal_report = None
    trace_executable_lite = False
    if single_operator_certificate and candidate_answer_type_supported:
        formal_report, formal_error = _validate_with_formal_verifier(
            normalized_record, normalized_certificate, applied_operator_ids[0]
        )
        if formal_error:
            notes.append(f"formal verifier unavailable: {formal_error}")
        if formal_report is not None:
            trace_executable_lite = bool(formal_report.get("trace_executable"))
            operator_match = operator_match and bool(formal_report.get("matches_operator"))
            incorrectness = bool(formal_report.get("is_incorrect"))
            unique_vs_correct = bool(formal_report.get("is_unique"))

    if formal_report is None and single_operator_certificate:
        trace_executable_lite = (
            has_wrong_trace and divergence_step_count == 1 and operator_match and derived_answer_present
        )

    if composite_certificate:
        trace_executable_lite = False

    if parse_failure:
        notes.append("answer equivalence used string fallback")

    return {
        "item_id": normalized_certificate.get("item_id") or normalized_record.get("item_id", ""),
        "certificate_id": normalized_certificate.get("certificate_id", ""),
        "item_role": normalized_certificate.get("item_role") or normalized_record.get("item_role", ""),
        "applied_operator_ids": applied_operator_ids,
        "candidate_answer": candidate_answer,
        "is_composite": composite_certificate,
        "has_candidate_answer": has_candidate_answer,
        "has_wrong_trace": has_wrong_trace,
        "candidate_answer_type_supported": candidate_answer_type_supported,
        "single_operator_certificate": single_operator_certificate,
        "composite_certificate": composite_certificate,
        "composite_deferred": composite_deferred,
        "divergence_step_count": divergence_step_count,
        "operator_match": operator_match,
        "derived_answer": derived_answer,
        "derived_answer_present": derived_answer_present,
        "answer_match": answer_match,
        "incorrectness": incorrectness,
        "unique_vs_correct": unique_vs_correct,
        "trace_executable_lite": trace_executable_lite,
        "parse_failure": parse_failure,
        "formal_report": formal_report,
        "notes": notes,
    }
