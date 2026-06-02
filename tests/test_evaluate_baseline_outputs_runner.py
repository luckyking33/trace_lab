from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


EVALUATE_SCRIPT = Path("scripts/evaluate_baseline_outputs.py")
GOLD_ORACLE_SCRIPT = Path("scripts/make_gold_oracle_baseline.py")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_certificate_audit(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "item_id",
                "certificate_id",
                "applied_operator_ids",
                "candidate_answer",
                "is_composite",
                "validation_status",
                "mev_status",
                "mev_v1",
                "parse_failure",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "item_id": "ITEM_SYMBOLIC",
                "certificate_id": "ITEM_SYMBOLIC::certificate_1",
                "applied_operator_ids": json.dumps(["ALG_DISTRIBUTIVE_DROP"]),
                "candidate_answer": json.dumps({"type": "formula", "value": "2*x"}),
                "is_composite": "false",
                "validation_status": "validated",
                "mev_status": "validated",
                "mev_v1": "1.0",
                "parse_failure": "false",
                "notes": "",
            }
        )
        writer.writerow(
            {
                "item_id": "ITEM_SYMBOLIC",
                "certificate_id": "ITEM_SYMBOLIC::deferred_composite",
                "applied_operator_ids": json.dumps(["ALG_DISTRIBUTIVE_DROP", "ALG_SIGN_MOVE"]),
                "candidate_answer": json.dumps({"type": "formula", "value": "3*x"}),
                "is_composite": "true",
                "validation_status": "deferred_composite",
                "mev_status": "deferred_composite",
                "mev_v1": "",
                "parse_failure": "false",
                "notes": "composite certificate deferred in v0",
            }
        )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_gold_oracle_output_evaluates_to_known_certificate_match_with_missing_cei(
    tmp_path: Path,
    payload_factory,
) -> None:
    items = tmp_path / "items.jsonl"
    certificate_audit = tmp_path / "certificate_audit.csv"
    generated = tmp_path / "gold_oracle_v1.jsonl"
    output_dir = tmp_path / "baseline_eval"
    item = payload_factory(
        answer_type="formula",
        correct_answer={"type": "formula", "value": "x"},
        allowed_operator_ids=["ALG_DISTRIBUTIVE_DROP"],
        question="Simplify x.",
        givens=[{"symbol": "x", "value": "x"}],
    )
    item["item_id"] = "ITEM_SYMBOLIC"
    _write_jsonl(items, [item])
    _write_certificate_audit(certificate_audit)

    oracle_result = subprocess.run(
        [
            sys.executable,
            str(GOLD_ORACLE_SCRIPT),
            "--certificate-audit",
            str(certificate_audit),
            "--items",
            str(items),
            "--output",
            str(generated),
            "--max-candidates-per-item",
            "3",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert oracle_result.returncode == 0, oracle_result.stderr

    evaluate_result = subprocess.run(
        [
            sys.executable,
            str(EVALUATE_SCRIPT),
            "--items",
            str(items),
            "--certificate-audit",
            str(certificate_audit),
            "--cei-audit",
            str(tmp_path / "missing_cei_pair_audit.csv"),
            "--generated",
            str(generated),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert evaluate_result.returncode == 0, evaluate_result.stderr
    for filename in [
        "candidate_eval.csv",
        "slate_eval.csv",
        "method_summary.json",
        "review_queue.jsonl",
        "invalid_candidates.jsonl",
    ]:
        assert (output_dir / filename).exists()

    summary = json.loads((output_dir / "method_summary.json").read_text(encoding="utf-8"))
    assert summary["known_certificate_match_rate"] == 1.0
    assert summary["matched_mev_v1_mean"] == 1.0
    assert summary["cei_status"] == "missing"
    assert summary["matched_cei_score_mean"] is None
    assert summary["matched_mdv_v1_mean"] is None

    candidate_rows = _read_csv(output_dir / "candidate_eval.csv")
    assert len(candidate_rows) == 1
    assert candidate_rows[0]["known_certificate_match"] == "true"
    assert candidate_rows[0]["matched_certificate_id"] == "ITEM_SYMBOLIC::certificate_1"
    assert candidate_rows[0]["final_certification_status"] == "known_certified"
    assert "matched_cei_status=missing" in candidate_rows[0]["notes"]

    slate_rows = _read_csv(output_dir / "slate_eval.csv")
    assert slate_rows[0]["mdv_status"] == "cei_missing"
