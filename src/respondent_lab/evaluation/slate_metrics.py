"""Slate-level metrics for Baseline Evaluator v0."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from itertools import combinations
from typing import Any


KNOWN_CERTIFIED = "known_certified"
SELF_CERTIFIED = "self_certified"


def compute_slate_metrics(
    candidate_eval_records: list[Any],
    certificate_bank_for_item: list[Any],
) -> dict[str, Any]:
    """Compute Baseline v0 slate metrics from evaluated candidate records."""

    records = [_plain(record) for record in candidate_eval_records or []]
    bank = [_plain(record) for record in certificate_bank_for_item or []]

    num_candidates = len(records)
    parse_success_count = sum(1 for record in records if bool(record.get("parse_success")))
    incorrect_count = sum(1 for record in records if record.get("incorrectness") is True)
    duplicate_answer_count = sum(1 for record in records if bool(record.get("duplicate_within_slate")))
    unique_answer_count = max(parse_success_count - duplicate_answer_count, 0)

    certified_records = [
        record
        for record in records
        if record.get("final_certification_status") in {KNOWN_CERTIFIED, SELF_CERTIFIED}
    ]
    known_certified_count = sum(
        1 for record in records if record.get("final_certification_status") == KNOWN_CERTIFIED
    )
    self_certified_count = sum(
        1 for record in records if record.get("final_certification_status") == SELF_CERTIFIED
    )

    bank_operator_ids = _unique_operator_ids(bank)
    certified_signatures = [
        tuple(_operator_ids_from_eval_record(record))
        for record in certified_records
        if _operator_ids_from_eval_record(record)
    ]
    covered_operator_ids = sorted({operator_id for sig in certified_signatures for operator_id in sig})
    if bank_operator_ids:
        operator_coverage = len(set(covered_operator_ids) & set(bank_operator_ids)) / len(bank_operator_ids)
    else:
        operator_coverage = 0.0

    answer_redundancy = duplicate_answer_count / parse_success_count if parse_success_count else 0.0
    operator_redundancy = _signature_redundancy(certified_signatures)
    mean_distance = _mean_pairwise_signature_distance(certified_signatures)

    mdv_values = [
        value
        for value in (_float_or_none(record.get("matched_mdv_v1")) for record in certified_records)
        if value is not None
    ]
    mev_values = [
        value
        for value in (_float_or_none(record.get("matched_mev_v1")) for record in certified_records)
        if value is not None
    ]
    mean_mev_v1_certified_only = _mean(mev_values)

    notes: list[str] = []
    mean_mdv_v1_certified_only: float | None = None
    slate_mdv_v1_lite: float | None = None
    if not certified_records:
        mdv_status = "no_certified_candidates"
        _add_note(notes, "no_certified_candidates")
    elif len(mdv_values) == len(certified_records):
        mdv_status = "ok"
        mean_mdv_v1_certified_only = _mean(mdv_values)
        slate_mdv_v1_lite = (
            mean_mdv_v1_certified_only
            + 0.3 * operator_coverage
            + 0.2 * mean_distance
            - 0.2 * operator_redundancy
        )
    else:
        mdv_status = "cei_missing"
        _add_note(notes, "mdv_v1_unavailable_for_certified_candidates")
        if mean_mev_v1_certified_only is not None:
            _add_note(notes, "mean_mev_v1_certified_only_used_as_fallback")

    if not bank_operator_ids:
        _add_note(notes, "no_certificate_bank_operators")

    return {
        "num_candidates": num_candidates,
        "parse_success_count": parse_success_count,
        "incorrect_count": incorrect_count,
        "unique_answer_count": unique_answer_count,
        "duplicate_answer_count": duplicate_answer_count,
        "known_certified_count": known_certified_count,
        "self_certified_count": self_certified_count,
        "certified_operator_ids": covered_operator_ids,
        "operator_coverage": operator_coverage,
        "answer_redundancy": answer_redundancy,
        "operator_redundancy": operator_redundancy,
        "mean_pairwise_signature_distance": mean_distance,
        "mean_mdv_v1_certified_only": mean_mdv_v1_certified_only,
        "mean_mev_v1_certified_only": mean_mev_v1_certified_only,
        "slate_mdv_v1_lite": slate_mdv_v1_lite,
        "mdv_status": mdv_status,
        "notes": notes,
    }


def _unique_operator_ids(records: list[Any]) -> list[str]:
    operators: set[str] = set()
    for record in records:
        operators.update(_operator_ids_from_bank_record(record))
    return sorted(operators)


def _operator_ids_from_bank_record(record: Any) -> list[str]:
    record = _plain(record)
    if not isinstance(record, dict):
        return []
    for key in ("operator_ids", "applied_operator_ids", "matched_operator_ids"):
        ids = _parse_sequence(record.get(key))
        if ids:
            return [str(operator_id) for operator_id in ids if operator_id]
    return [str(operator_id) for operator_id in _parse_sequence(record.get("operator_signature")) if operator_id]


def _operator_ids_from_eval_record(record: Any) -> list[str]:
    record = _plain(record)
    if not isinstance(record, dict):
        return []
    for key in ("matched_operator_ids", "operator_ids", "applied_operator_ids"):
        ids = _parse_sequence(record.get(key))
        if ids:
            return [str(operator_id) for operator_id in ids if operator_id]
    return [
        str(operator_id)
        for operator_id in _parse_sequence(record.get("matched_operator_signature"))
        if operator_id
    ]


def _signature_redundancy(signatures: list[tuple[str, ...]]) -> float:
    if not signatures:
        return 0.0
    return (len(signatures) - len(set(signatures))) / len(signatures)


def _mean_pairwise_signature_distance(signatures: list[tuple[str, ...]]) -> float:
    if len(signatures) < 2:
        return 0.0
    distances: list[float] = []
    for left, right in combinations(signatures, 2):
        left_set = set(left)
        right_set = set(right)
        union = left_set | right_set
        distances.append(1.0 - (len(left_set & right_set) / len(union)) if union else 0.0)
    return sum(distances) / len(distances)


def _parse_sequence(value: Any) -> list[Any]:
    value = _plain(value)
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str):
        parsed = _json_loads_or_none(value)
        if isinstance(parsed, list):
            return parsed
        stripped = value.strip()
        for separator in ("+", "|", ","):
            if separator in stripped:
                return [part.strip() for part in stripped.split(separator) if part.strip()]
        return [stripped] if stripped else []
    return [value]


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: _plain(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _json_loads_or_none(value: str) -> Any | None:
    try:
        return json.loads(value)
    except Exception:
        return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, "", "None", "none", "null"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _add_note(notes: list[str], note: str) -> None:
    if note not in notes:
        notes.append(note)
