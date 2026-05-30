"""Slate diversity and separability helpers."""

from __future__ import annotations

from itertools import combinations
from typing import Any


def operator_signature(applied_operator_ids: list[str]) -> tuple[str, ...]:
    """Return an order-preserving operator signature for a distractor."""

    return tuple(str(operator_id) for operator_id in applied_operator_ids)


def operator_coverage(allowed_operator_ids: list[str], signatures: list[tuple[str, ...]]) -> tuple[float, list[str]]:
    """Return covered operator fraction and the sorted covered operator ids."""

    allowed = {str(operator_id) for operator_id in allowed_operator_ids if operator_id}
    covered = {operator_id for signature in signatures for operator_id in signature}
    if not allowed:
        return 0.0, sorted(covered)
    return len(covered & allowed) / len(allowed), sorted(covered)


def redundancy(signatures: list[tuple[str, ...]]) -> float:
    """Return the share of distractors with duplicate operator signatures."""

    if not signatures:
        return 0.0
    return (len(signatures) - len(set(signatures))) / len(signatures)


def mean_pairwise_signature_distance(signatures: list[tuple[str, ...]]) -> float:
    """Return mean 1 - Jaccard distance across operator signature pairs."""

    if len(signatures) < 2:
        return 0.0
    distances: list[float] = []
    for left, right in combinations(signatures, 2):
        left_set = set(left)
        right_set = set(right)
        union = left_set | right_set
        if not union:
            distances.append(0.0)
            continue
        distances.append(1.0 - (len(left_set & right_set) / len(union)))
    return sum(distances) / len(distances)


def compute_signature_metrics(
    allowed_operator_ids: list[str], certificates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compute operator coverage, redundancy, and pairwise signature distance."""

    signatures = [operator_signature(certificate.get("applied_operator_ids") or []) for certificate in certificates]
    coverage, covered_operator_ids = operator_coverage(allowed_operator_ids, signatures)
    return {
        "covered_operator_ids": covered_operator_ids,
        "operator_coverage": coverage,
        "redundancy": redundancy(signatures),
        "mean_pairwise_signature_distance": mean_pairwise_signature_distance(signatures),
    }
