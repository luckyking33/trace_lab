"""Candidate-level mechanistic validity metrics."""

from __future__ import annotations

from typing import Any


MEV_COMPONENTS = [
    "has_candidate_answer",
    "has_wrong_trace",
    "incorrectness",
    "operator_match",
    "answer_match",
    "trace_executable_lite",
]


def compute_mev_lite(validation: dict[str, Any]) -> dict[str, Any]:
    """Return MEV-lite and the component booleans used to compute it."""

    components = {key: bool(validation.get(key)) for key in MEV_COMPONENTS}
    mev_lite = 1.0 if all(components.values()) else 0.0
    return {**components, "mev_lite": mev_lite}


def compute_mev_v1(validation_record: dict[str, Any]) -> dict[str, Any]:
    """Compute MEV v1 for a certificate validation record.

    MEV v1 is intentionally scoped to single-operator certificates. Composite
    certificates are deferred rather than scored because Audit v0 does not fully
    validate multi-operator paths.
    """

    composite = bool(
        validation_record.get("composite_deferred")
        or validation_record.get("composite_certificate")
        or validation_record.get("is_composite")
    )
    explicitly_deferred = bool(validation_record.get("deferred"))

    gates = {
        "gate_candidate_present": bool(validation_record.get("has_candidate_answer")),
        "gate_wrong_trace_present": bool(validation_record.get("has_wrong_trace")),
        "gate_incorrectness": bool(validation_record.get("incorrectness")),
        "gate_operator_match": bool(validation_record.get("operator_match")),
        "gate_answer_match": bool(validation_record.get("answer_match")),
        "gate_trace_executable": bool(validation_record.get("trace_executable_lite")),
    }

    notes = list(validation_record.get("notes") or [])
    divergence_step_count = int(validation_record.get("divergence_step_count") or 0)

    if composite or explicitly_deferred:
        if not any("deferred" in str(note).lower() for note in notes):
            notes.append("composite certificate deferred in v0")
        return {
            "mev_v1": None,
            "mev_status": "deferred_composite",
            **gates,
            "locality_score": None,
            "notes": notes,
        }

    locality_score = 1.0 if divergence_step_count == 1 else 0.0
    if locality_score == 0.0:
        notes.append("single-operator MEV v1 requires exactly one divergence step")

    gate_product = 1.0 if all(gates.values()) else 0.0
    mev_v1 = gate_product * locality_score
    mev_status = "validated" if mev_v1 == 1.0 else "failed"

    return {
        "mev_v1": mev_v1,
        "mev_status": mev_status,
        **gates,
        "locality_score": locality_score,
        "notes": notes,
    }
