from __future__ import annotations

import json
from pathlib import Path

from respondent_lab.evaluation.generated_outputs import (
    load_generated_outputs,
    normalize_generated_candidate,
)


def test_generated_output_loader_accepts_string_and_dict_answers(tmp_path: Path) -> None:
    generated = tmp_path / "generated.jsonl"
    generated.write_text(
        json.dumps(
            {
                "run_id": "run_fixture",
                "method": "fixture_method",
                "item_id": "ITEM_001",
                "candidates": [
                    {"candidate_id": "raw_string", "answer": "x + x"},
                    {"candidate_id": "answer_object", "answer": {"type": "formula", "value": "2*x"}},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    outputs = load_generated_outputs(generated)

    assert len(outputs) == 1
    assert outputs[0].item_id == "ITEM_001"
    assert outputs[0].candidates[0].answer == "x + x"
    assert outputs[0].candidates[1].answer == {"type": "formula", "value": "2*x"}

    raw_string = normalize_generated_candidate(outputs[0].candidates[0], item_answer_type="formula")
    answer_object = normalize_generated_candidate(outputs[0].candidates[1], item_answer_type="formula")
    assert raw_string["parse_success"] is True
    assert raw_string["normalized_answer"]["type"] == "formula"
    assert answer_object["parse_success"] is True
    assert answer_object["normalized_answer"]["value"] == "2*x"
