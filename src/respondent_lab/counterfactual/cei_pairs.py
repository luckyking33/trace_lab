"""Manual paired CEI record loading and validation."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from sympy import Symbol, simplify
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from respondent_lab.certificates.validation import answer_equivalent, validate_certificate
from respondent_lab.io.normalization import normalize_answer_object, strip_latex_wrappers
from respondent_lab.metrics.mechanistic_validity import compute_mev_v1


TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)


def load_cei_pairs(path: str | Path) -> list[dict[str, Any]]:
    """Load manually curated CEI pairs from JSONL."""

    cei_path = Path(path)
    if not cei_path.exists():
        raise FileNotFoundError(
            f"CEI pairs file not found: {cei_path}. Real paired CEI requires explicit "
            "manual CEI records; CEI-readiness labels are not CEI."
        )

    pairs: list[dict[str, Any]] = []
    with cei_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid CEI JSON on line {line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Expected CEI JSON object on line {line_number}")
            pairs.append(payload)
    return pairs


def _answer(raw: Any, default_type: str = "formula") -> dict[str, Any]:
    if isinstance(raw, dict) and "type" in raw and "value" in raw:
        return normalize_answer_object(raw)
    return normalize_answer_object({"type": default_type, "value": raw})


def _equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    equivalent, _parse_failure = answer_equivalent(left, right)
    return equivalent


def _substitute_value(value: Any, from_symbol: str | None, to_symbol: str | None) -> Any:
    if isinstance(value, list):
        return [_substitute_value(item, from_symbol, to_symbol) for item in value]
    if not from_symbol or not to_symbol:
        return value

    text = strip_latex_wrappers(str(value))
    try:
        expr = parse_expr(text, transformations=TRANSFORMATIONS, evaluate=False)
        substituted = expr.subs(Symbol(from_symbol), Symbol(to_symbol))
        return str(simplify(substituted))
    except Exception:  # noqa: BLE001 - fall back to conservative token replacement.
        return re.sub(rf"\b{re.escape(from_symbol)}\b", to_symbol, text)


def _mapped_source_answer(
    source_wrong_answer: dict[str, Any],
    mapping: dict[str, Any],
    transformed_answer_type: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    mapping_type = str(mapping.get("type") or "")
    notes: list[str] = []

    if mapping_type == "identity":
        return _answer(source_wrong_answer, transformed_answer_type), notes

    if mapping_type == "variable_substitution":
        source = _answer(source_wrong_answer, transformed_answer_type)
        mapped = copy.deepcopy(source)
        mapped["value"] = _substitute_value(
            mapped.get("value"),
            mapping.get("from_symbol"),
            mapping.get("to_symbol"),
        )
        if not mapping.get("from_symbol") or not mapping.get("to_symbol"):
            notes.append("variable_substitution mapping used no-op because from_symbol/to_symbol was absent")
        return normalize_answer_object(mapped), notes

    if mapping_type == "explicit_expected":
        if "expected_transformed_wrong_answer" not in mapping:
            notes.append("explicit_expected mapping missing expected_transformed_wrong_answer")
            return None, notes
        return _answer(mapping["expected_transformed_wrong_answer"], transformed_answer_type), notes

    notes.append(f"unsupported answer_mapping type: {mapping_type or '<missing>'}")
    return None, notes


def _minimal_transformed_record(pair: dict[str, Any]) -> dict[str, Any]:
    transformed_item = pair.get("transformed_item") or {}
    operator_id = str(pair.get("operator_id") or "")
    correct_answer = transformed_item.get("correct_answer") or {"type": "formula", "value": ""}
    answer_type = str(transformed_item.get("answer_type") or correct_answer.get("type") or "formula")

    return {
        "item_id": str(transformed_item.get("item_id") or f"{pair.get('cei_pair_id', '')}::transformed_item"),
        "subject": str(transformed_item.get("subject") or "math"),
        "domain": str(transformed_item.get("domain") or "math"),
        "question": str(transformed_item.get("question") or transformed_item.get("question_clean") or ""),
        "correct_answer": correct_answer,
        "answer_type": answer_type,
        "givens": transformed_item.get("givens") or [],
        "constraints": transformed_item.get("constraints") or [],
        "solution_trace": transformed_item.get("solution_trace") or [],
        "allowed_operator_ids": transformed_item.get("allowed_operator_ids") or ([operator_id] if operator_id else []),
        "counterfactual_transforms": transformed_item.get("counterfactual_transforms")
        or ([str(pair.get("transform_type"))] if pair.get("transform_type") else []),
        "leakage_flags": transformed_item.get("leakage_flags")
        or {
            "original_distractors_removed": True,
            "human_response_dist_removed": True,
            "seed_candidates_removed": True,
        },
        "item_role": "cei_transformed_item",
    }


def _transformed_certificate(pair: dict[str, Any], transformed_item_id: str) -> dict[str, Any]:
    certificate = copy.deepcopy(pair.get("transformed_certificate") or {})
    pair_id = str(pair.get("cei_pair_id") or "CEI_PAIR")
    certificate.setdefault("certificate_id", f"{pair_id}::transformed_certificate")
    certificate.setdefault("item_id", transformed_item_id)
    certificate.setdefault("item_role", "cei_transformed_item")
    return certificate


def _validate_transformed_certificate(pair: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    record = _minimal_transformed_record(pair)
    certificate = _transformed_certificate(pair, str(record.get("item_id") or ""))
    try:
        validation = validate_certificate(record, certificate)
        validation.update(compute_mev_v1(validation))
        return validation, notes
    except Exception as exc:  # noqa: BLE001 - CEI validation should report structured failure.
        notes.append(f"transformed certificate validation failed: {exc}")
        return {
            "mev_v1": 0.0,
            "mev_status": "failed",
            "notes": notes,
            "applied_operator_ids": certificate.get("applied_operator_ids") or [],
            "single_operator_certificate": len(certificate.get("applied_operator_ids") or []) == 1,
        }, notes


def _source_certificate_status(
    pair: dict[str, Any], source_certificate_lookup: dict[str, dict[str, Any]] | None
) -> tuple[str, bool, list[str]]:
    if source_certificate_lookup is None:
        return "not_checked", True, []

    source_certificate_id = str(pair.get("source_certificate_id") or "")
    source = source_certificate_lookup.get(source_certificate_id)
    if source is None:
        return "missing", False, [f"source certificate not found: {source_certificate_id}"]

    status = str(source.get("mev_status") or source.get("validation_status") or "")
    raw_mev_v1 = source.get("mev_v1")
    try:
        mev_v1 = float(raw_mev_v1)
    except (TypeError, ValueError):
        mev_v1 = None
    if status == "validated" and mev_v1 == 1.0:
        return "passed", True, []
    return "failed", False, [f"source certificate MEV v1 did not pass: status={status}, mev_v1={raw_mev_v1}"]


def validate_cei_pair(
    pair: dict[str, Any],
    source_certificate_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate one manually curated CEI pair."""

    notes: list[str] = []
    operator_id = str(pair.get("operator_id") or "")
    transformed_certificate = pair.get("transformed_certificate") or {}
    transformed_operator_ids = [
        str(item) for item in transformed_certificate.get("applied_operator_ids") or [] if item
    ]

    transformed_validation, transformed_notes = _validate_transformed_certificate(pair)
    notes.extend(transformed_notes)

    transformed_answer = _answer(
        transformed_certificate.get("candidate_answer") or {},
        str((pair.get("transformed_item") or {}).get("answer_type") or "formula"),
    )
    mapping = pair.get("answer_mapping") or {}
    mapped_source_answer, mapping_notes = _mapped_source_answer(
        pair.get("source_wrong_answer") or {},
        mapping,
        str(transformed_answer.get("type") or "formula"),
    )
    notes.extend(mapping_notes)
    answer_mapping_pass = bool(mapped_source_answer and _equivalent(mapped_source_answer, transformed_answer))
    if not answer_mapping_pass:
        notes.append("answer mapping did not match transformed wrong answer")

    source_status, source_pass, source_notes = _source_certificate_status(pair, source_certificate_lookup)
    notes.extend(source_notes)

    transformed_certificate_single_operator = len(transformed_operator_ids) == 1
    same_operator = transformed_certificate_single_operator and transformed_operator_ids == [operator_id]
    transformed_mev_v1 = transformed_validation.get("mev_v1")
    transformed_mev_v1_pass = transformed_validation.get("mev_status") == "validated" and transformed_mev_v1 == 1.0

    required_fields = {
        "has_pair_id": bool(pair.get("cei_pair_id")),
        "has_source_item_id": bool(pair.get("source_item_id")),
        "has_source_certificate_id": bool(pair.get("source_certificate_id")),
        "has_operator_id": bool(operator_id),
        "transform_type_present": bool(pair.get("transform_type")),
    }
    for field_name, passed in required_fields.items():
        if not passed:
            notes.append(f"missing required CEI field: {field_name}")

    cei_pair_pass = (
        all(required_fields.values())
        and transformed_certificate_single_operator
        and same_operator
        and transformed_mev_v1_pass
        and answer_mapping_pass
        and source_pass
    )

    return {
        "cei_pair_id": str(pair.get("cei_pair_id") or ""),
        "source_item_id": str(pair.get("source_item_id") or ""),
        "source_certificate_id": str(pair.get("source_certificate_id") or ""),
        "operator_id": operator_id,
        "transform_type": str(pair.get("transform_type") or ""),
        **required_fields,
        "transformed_certificate_single_operator": transformed_certificate_single_operator,
        "same_operator": same_operator,
        "transformed_certificate_mev_v1": transformed_mev_v1,
        "transformed_certificate_mev_v1_pass": transformed_mev_v1_pass,
        "answer_mapping_type": str(mapping.get("type") or ""),
        "answer_mapping_pass": answer_mapping_pass,
        "source_certificate_status": source_status,
        "cei_pair_pass": cei_pair_pass,
        "notes": notes,
    }
