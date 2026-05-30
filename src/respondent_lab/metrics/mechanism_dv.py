"""Slate-level mechanism diversity/validity metrics."""

from __future__ import annotations

from typing import Any

from respondent_lab.metrics.diagnostic_separability import compute_signature_metrics


def cei_readiness(record: dict[str, Any]) -> bool:
    """Return whether an item has non-empty declared counterfactual transforms."""

    transforms = record.get("counterfactual_transforms") or []
    return bool(transforms) and all(isinstance(item, str) and bool(item.strip()) for item in transforms)


def compute_slate_mdv_lite(
    record: dict[str, Any],
    certificates: list[dict[str, Any]],
    certificate_validations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute slate-level MDV-lite for items with a distractor_set."""

    signature_metrics = compute_signature_metrics(record.get("allowed_operator_ids") or [], certificates)
    candidate_scores = [float(validation.get("mev_lite", 0.0)) for validation in certificate_validations]
    mean_candidate_mev_lite = sum(candidate_scores) / len(candidate_scores) if candidate_scores else 0.0
    slate_mdv_lite = (
        mean_candidate_mev_lite
        + 0.3 * signature_metrics["operator_coverage"]
        + 0.2 * signature_metrics["mean_pairwise_signature_distance"]
        - 0.2 * signature_metrics["redundancy"]
    )
    return {
        **signature_metrics,
        "mean_candidate_mev_lite": mean_candidate_mev_lite,
        "slate_mdv_lite": slate_mdv_lite,
    }
