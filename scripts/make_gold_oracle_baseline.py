#!/usr/bin/env python3
"""Create a certificate-bank gold-oracle JSONL for evaluator sanity checks."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from respondent_lab.evaluation.certificate_bank import build_certificate_bank  # noqa: E402
from respondent_lab.io.math_dataset_loader import load_and_normalize_math_items  # noqa: E402


def make_gold_oracle(
    *,
    certificate_audit: Path,
    items: Path,
    output: Path,
    max_candidates_per_item: int,
) -> dict[str, Any]:
    item_records = load_and_normalize_math_items(items)
    certificate_bank = build_certificate_bank(certificate_audit, None)
    bank_by_item = _group_by_item_id(certificate_bank)

    output.parent.mkdir(parents=True, exist_ok=True)
    run_id = output.stem
    total_candidates = 0
    rows: list[dict[str, Any]] = []

    for item_record in item_records:
        item_id = str(item_record.get("item_id") or "")
        candidates = []
        for index, bank_record in enumerate(bank_by_item.get(item_id, [])[: max(0, max_candidates_per_item)], start=1):
            candidates.append(
                {
                    "candidate_id": f"gold_oracle_{index}",
                    "answer": bank_record.get("candidate_answer"),
                    "metadata": {
                        "oracle_sanity_check": True,
                        "source_certificate_id": bank_record.get("certificate_id"),
                        "source_operator_ids": bank_record.get("operator_ids"),
                    },
                }
            )
        total_candidates += len(candidates)
        rows.append(
            {
                "run_id": run_id,
                "method": "gold_oracle_sanity",
                "item_id": item_id,
                "candidates": candidates,
                "metadata": {
                    "not_real_baseline": True,
                    "oracle_sanity_check": True,
                    "selection": "validated_single_operator_non_composite_bank_answers",
                },
            }
        )

    _write_jsonl(output, rows)
    return {
        "run_id": run_id,
        "method": "gold_oracle_sanity",
        "num_items": len(rows),
        "num_candidates": total_candidates,
        "max_candidates_per_item": max_candidates_per_item,
        "oracle_sanity_check": True,
        "not_real_baseline": True,
    }


def _group_by_item_id(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("item_id") or "")].append(record)
    return dict(grouped)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            json.dump(row, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate-audit", required=True, type=Path)
    parser.add_argument("--items", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-candidates-per-item", default=3, type=int)
    args = parser.parse_args()

    try:
        summary = make_gold_oracle(
            certificate_audit=args.certificate_audit,
            items=args.items,
            output=args.output,
            max_candidates_per_item=args.max_candidates_per_item,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
