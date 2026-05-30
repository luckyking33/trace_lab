"""Extract normalized certificate records from curated math items."""

from __future__ import annotations

import copy
from typing import Any


def _operator_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if item]


def _certificate(
    *,
    record: dict[str, Any],
    certificate_id: str,
    applied_operator_ids: list[str],
    candidate_answer: dict[str, Any] | None,
    wrong_solution_trace: list[dict[str, Any]],
    mechanism_note: str,
) -> dict[str, Any]:
    return {
        "item_id": record.get("item_id", ""),
        "item_role": record.get("item_role", ""),
        "certificate_id": certificate_id,
        "applied_operator_ids": applied_operator_ids,
        "candidate_answer": copy.deepcopy(candidate_answer) if candidate_answer else {},
        "wrong_solution_trace": copy.deepcopy(wrong_solution_trace or []),
        "mechanism_note": mechanism_note,
        "is_composite": len(applied_operator_ids) > 1,
    }


def extract_certificates(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one certificate per manually supplied distractor path."""

    item_id = str(record.get("item_id") or "")
    certificates: list[dict[str, Any]] = []

    if record.get("distractor_answer") and record.get("wrong_solution_trace"):
        operator_ids = _operator_ids(record.get("target_error_operator_id"))
        if not operator_ids:
            operator_ids = _operator_ids(record.get("target_error_operator_ids"))
        certificates.append(
            _certificate(
                record=record,
                certificate_id=f"{item_id}::certificate_1",
                applied_operator_ids=operator_ids,
                candidate_answer=record.get("distractor_answer"),
                wrong_solution_trace=record.get("wrong_solution_trace") or [],
                mechanism_note=str(record.get("mechanism_note") or ""),
            )
        )

    for index, distractor in enumerate(record.get("distractor_set") or [], start=1):
        certificate_id = str(distractor.get("distractor_id") or f"{item_id}::distractor_{index}")
        certificates.append(
            _certificate(
                record=record,
                certificate_id=certificate_id,
                applied_operator_ids=_operator_ids(distractor.get("applied_operator_ids")),
                candidate_answer=distractor.get("answer"),
                wrong_solution_trace=distractor.get("wrong_solution_trace") or [],
                mechanism_note=str(distractor.get("mechanism_note") or record.get("mechanism_note") or ""),
            )
        )

    return certificates
