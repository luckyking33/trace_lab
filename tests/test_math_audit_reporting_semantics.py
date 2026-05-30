from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/audit_math_certificates.py")


def _jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_deferred_composites_are_not_hard_failures(tmp_path: Path, payload_factory) -> None:
    data = tmp_path / "items.jsonl"
    output_dir = tmp_path / "audit"
    record = payload_factory(
        question="Solve for x: 3x - 5 = 16.",
        givens=[{"symbol": "equation", "value": "3*x - 5 = 16"}],
        correct_answer={"type": "numeric", "value": "7"},
        answer_type="numeric",
        allowed_operator_ids=["ALG_SIGN_MOVE", "ALG_DISTRIBUTIVE_DROP"],
    )
    record["item_role"] = "transfer_item"
    record["distractor_set"] = [
        {
            "distractor_id": "TEST_001_D3",
            "applied_operator_ids": ["ALG_SIGN_MOVE", "ALG_DISTRIBUTIVE_DROP"],
            "answer": {"type": "numeric", "value": "9"},
            "wrong_solution_trace": [
                {"step_id": 1, "expr": "3*x - 5 = 16", "operation": "given", "metadata": {}},
                {
                    "step_id": 2,
                    "expr": "3*x = 16 - 5",
                    "operation": "move -5 without changing sign",
                    "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
                },
                {
                    "step_id": 3,
                    "expr": "x = 9",
                    "operation": "drop distribution in downstream step",
                    "result": "9",
                    "metadata": {"error_operator_id": "ALG_DISTRIBUTIVE_DROP", "derived_answer": "9"},
                },
            ],
        }
    ]
    data.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(data), "--output-dir", str(output_dir)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert _jsonl_rows(output_dir / "failures.jsonl") == []
    deferred_rows = _jsonl_rows(output_dir / "deferred.jsonl")
    assert len(deferred_rows) == 1
    assert deferred_rows[0]["certificate_id"] == "TEST_001_D3"

    summary = json.loads((output_dir / "dataset_summary.json").read_text(encoding="utf-8"))
    assert summary["hard_failure_count"] == 0
    assert summary["deferred_count"] == 1
    assert summary["validated_scope"] == "single_operator_single_divergence"

    with (output_dir / "certificate_audit.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["validation_status"] == "deferred_composite"
    assert rows[0]["failure_type"] == ""
    assert rows[0]["deferred_reason"] == "composite_certificate_deferred_in_v0"
