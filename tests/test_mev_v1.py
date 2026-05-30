from __future__ import annotations

from respondent_lab.metrics.mechanistic_validity import compute_mev_v1


def test_validated_single_operator_certificate_gets_mev_v1_one() -> None:
    validation = {
        "has_candidate_answer": True,
        "has_wrong_trace": True,
        "incorrectness": True,
        "operator_match": True,
        "answer_match": True,
        "trace_executable_lite": True,
        "single_operator_certificate": True,
        "composite_deferred": False,
        "divergence_step_count": 1,
        "notes": [],
    }

    result = compute_mev_v1(validation)

    assert result["mev_status"] == "validated"
    assert result["mev_v1"] == 1.0
    assert result["locality_score"] == 1.0


def test_composite_deferred_certificate_gets_no_mev_v1_score() -> None:
    validation = {
        "has_candidate_answer": True,
        "has_wrong_trace": True,
        "incorrectness": True,
        "operator_match": True,
        "answer_match": True,
        "trace_executable_lite": False,
        "composite_deferred": True,
        "divergence_step_count": 2,
        "notes": ["composite certificate deferred in v0"],
    }

    result = compute_mev_v1(validation)

    assert result["mev_status"] == "deferred_composite"
    assert result["mev_v1"] is None
    assert result["locality_score"] is None
