from __future__ import annotations

from respondent_lab.evaluation.baseline_evaluator import evaluate_generated_item


def _symbolic_item() -> dict:
    return {
        "item_id": "ITEM_SYMBOLIC",
        "subject": "math",
        "domain": "algebra",
        "question": "Simplify x.",
        "answer_type": "formula",
        "correct_answer": {"type": "formula", "value": "x"},
        "givens": [{"symbol": "x", "value": "x"}],
        "constraints": [],
        "solution_trace": [],
        "allowed_operator_ids": ["ALG_DISTRIBUTIVE_DROP"],
        "counterfactual_transforms": [],
        "leakage_flags": {},
    }


def _certificate_bank() -> list[dict]:
    return [
        {
            "item_id": "ITEM_SYMBOLIC",
            "certificate_id": "ITEM_SYMBOLIC::certificate_1",
            "candidate_answer": {"type": "formula", "value": "2*x"},
            "operator_ids": ["ALG_DISTRIBUTIVE_DROP"],
            "operator_signature": "ALG_DISTRIBUTIVE_DROP",
            "mev_v1": 1.0,
            "cei_score": 1.0,
            "cei_pair_count": 2,
            "mdv_v1": 1.0,
            "validation_scope": "single_operator_single_divergence",
            "cei_status": "passed",
        }
    ]


def test_evaluator_marks_symbolic_match_review_correct_equivalent_and_duplicate() -> None:
    generated_output = {
        "item_id": "ITEM_SYMBOLIC",
        "candidates": [
            {"candidate_id": "known_symbolic", "answer": "x + x"},
            {"candidate_id": "review", "answer": "3*x"},
            {"candidate_id": "correct", "answer": "x"},
            {"candidate_id": "duplicate", "answer": "2*x"},
        ],
    }

    result = evaluate_generated_item(_symbolic_item(), generated_output, _certificate_bank())
    by_id = {record["candidate_id"]: record for record in result["candidate_evaluations"]}

    assert by_id["known_symbolic"]["known_certificate_match"] is True
    assert by_id["known_symbolic"]["matched_certificate_id"] == "ITEM_SYMBOLIC::certificate_1"
    assert by_id["known_symbolic"]["final_certification_status"] == "known_certified"

    assert by_id["review"]["known_certificate_match"] is False
    assert by_id["review"]["incorrectness"] is True
    assert by_id["review"]["final_certification_status"] == "incorrect_unmatched_review"

    assert by_id["correct"]["incorrectness"] is False
    assert by_id["correct"]["final_certification_status"] == "invalid_equivalent_to_correct"

    assert by_id["duplicate"]["duplicate_within_slate"] is True
    assert by_id["duplicate"]["duplicate_of_candidate_id"] == "known_symbolic"
    assert by_id["duplicate"]["final_certification_status"] == "invalid_duplicate"
