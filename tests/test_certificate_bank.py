from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from respondent_lab.evaluation.certificate_bank import build_certificate_bank


CERTIFICATE_AUDIT_FIELDS = [
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
]

CEI_AUDIT_FIELDS = ["source_certificate_id", "cei_pair_pass"]


def _write_certificate_audit(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CERTIFICATE_AUDIT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "item_id": row.get("item_id", "ITEM_001"),
                    "certificate_id": row["certificate_id"],
                    "applied_operator_ids": json.dumps(row.get("applied_operator_ids", ["ALG_SIGN_MOVE"])),
                    "candidate_answer": json.dumps(row.get("candidate_answer", {"type": "numeric", "value": "11"})),
                    "is_composite": str(row.get("is_composite", False)).lower(),
                    "validation_status": row.get("validation_status", "validated"),
                    "mev_status": row.get("mev_status", "validated"),
                    "mev_v1": row.get("mev_v1", "1.0"),
                    "parse_failure": str(row.get("parse_failure", False)).lower(),
                    "notes": row.get("notes", ""),
                }
            )


def _write_cei_audit(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CEI_AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_certificate_bank_excludes_deferred_composites_and_includes_validated_single_operator(
    tmp_path: Path,
) -> None:
    audit = tmp_path / "certificate_audit.csv"
    _write_certificate_audit(
        audit,
        [
            {
                "certificate_id": "ITEM_001::certificate_1",
                "applied_operator_ids": ["ALG_SIGN_MOVE"],
                "candidate_answer": {"type": "numeric", "value": "11/3"},
            },
            {
                "certificate_id": "ITEM_001::composite",
                "applied_operator_ids": ["ALG_SIGN_MOVE", "ALG_ILLEGAL_CANCEL"],
                "candidate_answer": {"type": "numeric", "value": "4"},
                "is_composite": True,
                "validation_status": "deferred_composite",
                "mev_status": "deferred_composite",
                "mev_v1": "",
            },
        ],
    )

    bank = build_certificate_bank(audit, None)

    assert [record["certificate_id"] for record in bank] == ["ITEM_001::certificate_1"]
    assert bank[0]["operator_ids"] == ["ALG_SIGN_MOVE"]
    assert bank[0]["normalized_answer_type"] == "numeric"
    assert bank[0]["validation_scope"] == "single_operator_single_divergence"


def test_cei_aggregation_computes_pass_count_over_total_count(tmp_path: Path) -> None:
    audit = tmp_path / "certificate_audit.csv"
    cei = tmp_path / "cei_pair_audit.csv"
    _write_certificate_audit(audit, [{"certificate_id": "ITEM_001::certificate_1"}])
    _write_cei_audit(
        cei,
        [
            {"source_certificate_id": "ITEM_001::certificate_1", "cei_pair_pass": "true"},
            {"source_certificate_id": "ITEM_001::certificate_1", "cei_pair_pass": "false"},
            {"source_certificate_id": "ITEM_001::certificate_1", "cei_pair_pass": "true"},
        ],
    )

    bank = build_certificate_bank(audit, cei)

    assert len(bank) == 1
    assert bank[0]["cei_pair_count"] == 3
    assert bank[0]["cei_score"] == pytest.approx(2 / 3)
    assert bank[0]["mdv_v1"] == pytest.approx(2 / 3)
    assert bank[0]["cei_status"] == "partial"


def test_missing_cei_audit_marks_bank_records_missing_without_crashing(tmp_path: Path) -> None:
    audit = tmp_path / "certificate_audit.csv"
    _write_certificate_audit(audit, [{"certificate_id": "ITEM_001::certificate_1"}])

    bank = build_certificate_bank(audit, tmp_path / "missing_cei_pair_audit.csv")

    assert len(bank) == 1
    assert bank[0]["cei_status"] == "missing"
    assert bank[0]["cei_score"] is None
    assert bank[0]["cei_pair_count"] == 0
    assert bank[0]["mdv_v1"] is None
