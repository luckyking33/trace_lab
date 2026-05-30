from __future__ import annotations

import json
from pathlib import Path

from respondent_lab.io.math_dataset_loader import load_and_normalize_math_items
from respondent_lab.io.normalization import (
    normalize_answer_type,
    normalize_trace_steps,
    strip_latex_wrappers,
)


def test_answer_type_mapping_symbolic_and_set_numeric() -> None:
    assert normalize_answer_type("symbolic")[0] == "formula"
    assert normalize_answer_type("set_numeric")[0] == "answer_set"


def test_strip_latex_wrappers_common_constructs() -> None:
    assert strip_latex_wrappers(r"\(\frac{8}{3}\)") == "(8)/(3)"
    assert strip_latex_wrappers(r"\sqrt{31}") == "sqrt(31)"
    assert strip_latex_wrappers(r"\pm 7") == "+- 7"


def test_trace_metadata_error_operator_marks_divergence() -> None:
    steps = [
        {
            "step_id": 1,
            "expr": "x = 1",
            "operation": "wrong move",
            "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
        }
    ]
    normalized = normalize_trace_steps(steps)
    assert normalized[0]["operator_id"] == "ALG_SIGN_MOVE"
    assert normalized[0]["is_divergence"] is True


def test_negative_controls_do_not_crash_loader(tmp_path: Path) -> None:
    path = tmp_path / "items.jsonl"
    record = {
        "item_id": "NEG_001",
        "item_role": "operator_unit_negative",
        "source": "manual",
        "subject": "math",
        "domain": "algebra",
        "question": r"Solve \(4x=20\).",
        "correct_answer": {"type": "set_numeric", "value": [r"\(5\)"]},
        "answer_type": "set_numeric",
        "givens": [{"symbol": "equation", "value": r"\(4x=20\)"}],
        "constraints": [],
        "solution_trace": [
            {"step_id": 1, "expr": r"\(4x=20\)", "operation": "given", "metadata": {}},
            {
                "step_id": 2,
                "expr": r"\(x=5\)",
                "operation": "solve",
                "result": [r"\(5\)"],
                "metadata": {"derived_answer": [r"\(5\)"]},
            },
        ],
        "allowed_operator_ids": [],
        "target_error_operator_ids": [],
        "negative_control_for_operator_id": "ALG_SIGN_MOVE",
        "counterfactual_transforms": ["scale_transform"],
        "leakage_flags": {
            "original_distractors_removed": True,
            "human_response_dist_removed": True,
            "seed_candidates_removed": True,
        },
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    loaded = load_and_normalize_math_items(path)
    assert loaded[0]["allowed_operator_ids"] == []
    assert loaded[0]["answer_type"] == "answer_set"
    assert loaded[0]["correct_answer"]["value"] == ["5"]
