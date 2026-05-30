from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from respondent_lab.counterfactual.cei_pairs import validate_cei_pair


SCRIPT = Path("scripts/run_math_cei_pairs.py")


def _base_pair() -> dict:
    return {
        "cei_pair_id": "CEI_MATH_001_VAR_RENAME",
        "source_item_id": "MATH_SRC_001",
        "source_certificate_id": "MATH_SRC_001_D1",
        "operator_id": "ALG_SIGN_MOVE",
        "transform_type": "variable_renaming",
        "source_wrong_answer": {"type": "numeric", "value": "11/3"},
        "transformed_item": {
            "item_id": "MATH_SRC_001_VAR",
            "subject": "math",
            "domain": "algebra",
            "question_clean": "Solve for y: 3y - 5 = 16.",
            "correct_answer": {"type": "numeric", "value": "7"},
            "answer_type": "numeric",
            "givens": [{"symbol": "equation", "value": "3*y - 5 = 16"}],
            "solution_trace": [
                {"step_id": 1, "expr": "3*y - 5 = 16", "operation": "given", "metadata": {}},
                {
                    "step_id": 2,
                    "expr": "y = 7",
                    "operation": "solve",
                    "result": "7",
                    "metadata": {"derived_answer": "7"},
                },
            ],
        },
        "transformed_certificate": {
            "candidate_answer": {"type": "numeric", "value": "11/3"},
            "wrong_solution_trace": [
                {"step_id": 1, "expr": "3*y - 5 = 16", "operation": "given", "metadata": {}},
                {
                    "step_id": 2,
                    "expr": "3*y = 16 - 5",
                    "operation": "move -5 without changing sign",
                    "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
                },
                {
                    "step_id": 3,
                    "expr": "y = 11/3",
                    "operation": "divide by 3",
                    "result": "11/3",
                    "metadata": {"derived_answer": "11/3"},
                },
            ],
            "applied_operator_ids": ["ALG_SIGN_MOVE"],
        },
        "answer_mapping": {"type": "identity"},
    }


def _source_lookup() -> dict[str, dict]:
    return {"MATH_SRC_001_D1": {"certificate_id": "MATH_SRC_001_D1", "mev_status": "validated", "mev_v1": "1.0"}}


def test_identity_answer_mapping_passes_for_equivalent_answers() -> None:
    result = validate_cei_pair(_base_pair(), _source_lookup())

    assert result["answer_mapping_pass"] is True
    assert result["transformed_certificate_mev_v1"] == 1.0
    assert result["cei_pair_pass"] is True


def test_identity_answer_mapping_fails_when_answers_differ() -> None:
    pair = _base_pair()
    pair["transformed_certificate"]["candidate_answer"] = {"type": "numeric", "value": "4"}
    pair["transformed_certificate"]["wrong_solution_trace"][-1]["result"] = "4"
    pair["transformed_certificate"]["wrong_solution_trace"][-1]["metadata"]["derived_answer"] = "4"

    result = validate_cei_pair(pair, _source_lookup())

    assert result["answer_mapping_pass"] is False
    assert result["cei_pair_pass"] is False


def test_variable_substitution_mapping_handles_simple_expression() -> None:
    pair = _base_pair()
    pair["source_wrong_answer"] = {"type": "formula", "value": "x + 1"}
    pair["transformed_item"]["answer_type"] = "formula"
    pair["transformed_item"]["correct_answer"] = {"type": "formula", "value": "y"}
    pair["transformed_certificate"]["candidate_answer"] = {"type": "formula", "value": "y + 1"}
    pair["transformed_certificate"]["wrong_solution_trace"][-1]["result"] = "y + 1"
    pair["transformed_certificate"]["wrong_solution_trace"][-1]["metadata"]["derived_answer"] = "y + 1"
    pair["answer_mapping"] = {
        "type": "variable_substitution",
        "from_symbol": "x",
        "to_symbol": "y",
    }

    result = validate_cei_pair(pair, _source_lookup())

    assert result["answer_mapping_pass"] is True
    assert result["cei_pair_pass"] is True


def test_run_math_cei_pairs_writes_summary_and_audit(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    output_dir = tmp_path / "cei"
    cei_pairs = tmp_path / "math_cei_pairs.jsonl"
    audit_dir.mkdir()
    with (audit_dir / "certificate_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["certificate_id", "mev_status", "mev_v1"])
        writer.writeheader()
        writer.writerow({"certificate_id": "MATH_SRC_001_D1", "mev_status": "validated", "mev_v1": "1.0"})
    cei_pairs.write_text(json.dumps(_base_pair()) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--audit-dir",
            str(audit_dir),
            "--cei-pairs",
            str(cei_pairs),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((output_dir / "cei_summary.json").read_text(encoding="utf-8"))
    assert summary["total_cei_pairs"] == 1
    assert summary["cei_pass_rate_overall"] == 1.0
    assert (output_dir / "cei_pair_audit.csv").exists()


def test_missing_math_cei_pairs_file_fails_clearly(tmp_path: Path) -> None:
    output_dir = tmp_path / "cei"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--audit-dir",
            str(tmp_path / "audit"),
            "--cei-pairs",
            str(tmp_path / "missing_math_cei_pairs.jsonl"),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "CEI pairs file not found" in result.stderr
    assert "CEI-readiness labels are not CEI" in result.stderr
    assert not (output_dir / "cei_summary.json").exists()
