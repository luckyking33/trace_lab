from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/audit_math_certificates.py")


def test_runner_produces_all_output_files(tmp_path: Path, payload_factory) -> None:
    data = tmp_path / "items.jsonl"
    output_dir = tmp_path / "audit"
    record = payload_factory(
        question="Solve for x: 3x - 5 = 16.",
        givens=[{"symbol": "equation", "value": "3*x - 5 = 16"}],
        correct_answer={"type": "numeric", "value": "7"},
        answer_type="numeric",
        allowed_operator_ids=["ALG_SIGN_MOVE"],
    )
    record["item_role"] = "operator_unit_positive"
    record["target_error_operator_id"] = "ALG_SIGN_MOVE"
    record["distractor_answer"] = {"type": "numeric", "value": "11/3"}
    record["wrong_solution_trace"] = [
        {"step_id": 1, "expr": "3*x - 5 = 16", "operation": "given", "metadata": {}},
        {
            "step_id": 2,
            "expr": "3*x = 16 - 5",
            "operation": "move -5 to the right but keep its sign",
            "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
        },
        {
            "step_id": 3,
            "expr": "x = 11/3",
            "operation": "divide by 3",
            "result": "11/3",
            "metadata": {"derived_answer": "11/3"},
        },
    ]
    data.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(data), "--output-dir", str(output_dir)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    for filename in [
        "dataset_summary.json",
        "item_audit.csv",
        "certificate_audit.csv",
        "slate_audit.csv",
        "failures.jsonl",
    ]:
        assert (output_dir / filename).exists()
    summary = json.loads((output_dir / "dataset_summary.json").read_text(encoding="utf-8"))
    assert summary["total_items"] == 1
    assert summary["total_certificates"] == 1
