from __future__ import annotations

from respondent_lab.certificates.validation import answer_equivalent, validate_certificate


def test_composite_certificate_is_marked_deferred(payload_factory) -> None:
    record = payload_factory()
    certificate = {
        "item_id": record["item_id"],
        "item_role": "transfer_item",
        "certificate_id": "COMPOSITE",
        "applied_operator_ids": ["ALG_SIGN_MOVE", "ALG_DISTRIBUTIVE_DROP"],
        "candidate_answer": {"type": "numeric", "value": "9"},
        "wrong_solution_trace": [
            {
                "step_id": 1,
                "expr": "3*x - 5 = 16",
                "operation": "given",
                "metadata": {},
            },
            {
                "step_id": 2,
                "expr": "3*x = 16 - 5",
                "operation": "sign move",
                "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
            },
            {
                "step_id": 3,
                "expr": "x = 9",
                "operation": "distribution drop",
                "result": "9",
                "metadata": {"error_operator_id": "ALG_DISTRIBUTIVE_DROP", "derived_answer": "9"},
            },
        ],
        "is_composite": True,
    }

    validation = validate_certificate(record, certificate)
    assert validation["composite_deferred"] is True
    assert validation["trace_executable_lite"] is False


def test_answer_set_equality_requires_exact_set_equality() -> None:
    candidate = {"type": "answer_set", "value": ["5"]}
    correct = {"type": "answer_set", "value": ["-1", "5"]}

    equivalent, parse_failure = answer_equivalent(candidate, correct)
    assert equivalent is False
    assert parse_failure is False
