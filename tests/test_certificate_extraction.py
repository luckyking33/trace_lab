from __future__ import annotations

from respondent_lab.certificates.extraction import extract_certificates


def test_distractor_set_extracts_multiple_certificates() -> None:
    record = {
        "item_id": "TRANS_001",
        "item_role": "transfer_item",
        "distractor_set": [
            {
                "distractor_id": "D1",
                "applied_operator_ids": ["ALG_SIGN_MOVE"],
                "answer": {"type": "numeric", "value": "1"},
                "wrong_solution_trace": [{"step_id": 1, "expr": "x=1", "operation": "solve"}],
            },
            {
                "distractor_id": "D2",
                "applied_operator_ids": ["ALG_SIGN_MOVE", "ALG_DISTRIBUTIVE_DROP"],
                "answer": {"type": "numeric", "value": "2"},
                "wrong_solution_trace": [{"step_id": 1, "expr": "x=2", "operation": "solve"}],
            },
        ],
    }

    certificates = extract_certificates(record)
    assert [certificate["certificate_id"] for certificate in certificates] == ["D1", "D2"]
    assert certificates[0]["is_composite"] is False
    assert certificates[1]["is_composite"] is True
