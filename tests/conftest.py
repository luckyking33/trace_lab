from __future__ import annotations

import copy
from typing import Any

import pytest


def make_payload(
    *,
    subject: str = "math",
    domain: str = "algebra",
    answer_type: str = "numeric",
    correct_answer: dict[str, Any] | None = None,
    givens: list[dict[str, Any]] | None = None,
    constraints: list[dict[str, Any]] | None = None,
    allowed_operator_ids: list[str] | None = None,
    question: str = "Canonical test item.",
) -> dict[str, Any]:
    if correct_answer is None:
        correct_answer = {"type": answer_type, "value": "7"}
    return {
        "item_id": "TEST_001",
        "subject": subject,
        "domain": domain,
        "question": question,
        "correct_answer": correct_answer,
        "answer_type": answer_type,
        "givens": givens or [{"symbol": "equation", "value": "3*x - 5 = 16"}],
        "constraints": constraints or [],
        "solution_trace": [
            {"step_id": 1, "expr": "given", "operation": "given", "metadata": {}},
            {
                "step_id": 2,
                "expr": "final",
                "operation": "solve",
                "result": str(correct_answer["value"]),
                "metadata": {"derived_answer": correct_answer},
            },
        ],
        "allowed_operator_ids": allowed_operator_ids or ["ALG_SIGN_MOVE"],
        "counterfactual_transforms": ["variable_renaming"],
        "leakage_flags": {
            "original_distractors_removed": True,
            "human_response_dist_removed": True,
            "seed_candidates_removed": True,
        },
    }


@pytest.fixture
def payload_factory():
    def factory(**kwargs: Any) -> dict[str, Any]:
        return copy.deepcopy(make_payload(**kwargs))

    return factory
