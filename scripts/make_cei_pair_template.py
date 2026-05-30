#!/usr/bin/env python3
"""Create blank manual annotation templates for math CEI pairs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


TRANSFORM_TYPES = ["variable_renaming", "numeric_perturbation"]


def _parse_json_cell(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _bool_cell(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def _is_validated_single_operator(row: dict[str, str]) -> bool:
    if row.get("validation_status"):
        return row.get("validation_status") == "validated" and not _bool_cell(row.get("is_composite"))
    return row.get("mev_lite") == "1.0" and not _bool_cell(row.get("is_composite"))


def _operator_id(row: dict[str, str]) -> str:
    operator_ids = _parse_json_cell(row.get("applied_operator_ids"))
    if isinstance(operator_ids, list) and operator_ids:
        return str(operator_ids[0])
    return ""


def _candidate_answer(row: dict[str, str]) -> dict[str, Any]:
    candidate = _parse_json_cell(row.get("candidate_answer"))
    if isinstance(candidate, dict) and "type" in candidate and "value" in candidate:
        answer = {"type": candidate.get("type"), "value": candidate.get("value")}
        if candidate.get("unit"):
            answer["unit"] = candidate["unit"]
        return answer
    return {"type": "TODO", "value": "TODO"}


def make_templates(audit_dir: Path, output_path: Path, max_per_operator: int) -> list[dict[str, Any]]:
    audit_csv = audit_dir / "certificate_audit.csv"
    if not audit_csv.exists():
        raise FileNotFoundError(f"certificate audit CSV not found: {audit_csv}")

    with audit_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    selected_counts: Counter[str] = Counter()
    templates: list[dict[str, Any]] = []
    for row in rows:
        if not _is_validated_single_operator(row):
            continue
        operator_id = _operator_id(row)
        if not operator_id or selected_counts[operator_id] >= max_per_operator:
            continue
        selected_counts[operator_id] += 1

        for transform_type in TRANSFORM_TYPES:
            template_index = selected_counts[operator_id]
            templates.append(
                {
                    "cei_pair_id": f"TODO_{operator_id}_{template_index}_{transform_type.upper()}",
                    "source_item_id": row.get("item_id") or "",
                    "source_certificate_id": row.get("certificate_id") or "",
                    "operator_id": operator_id,
                    "transform_type": transform_type,
                    "source_wrong_answer": _candidate_answer(row),
                    "transformed_item": {
                        "item_id": "TODO",
                        "subject": "math",
                        "domain": "TODO",
                        "question_clean": "TODO",
                        "correct_answer": {"type": "TODO", "value": "TODO"},
                        "answer_type": "TODO",
                        "solution_trace": [],
                    },
                    "transformed_certificate": {
                        "candidate_answer": {"type": "TODO", "value": "TODO"},
                        "wrong_solution_trace": [],
                        "applied_operator_ids": [],
                    },
                    "answer_mapping": {"type": "TODO"},
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for template in templates:
            json.dump(template, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    return templates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-per-operator", type=int, default=2)
    args = parser.parse_args()

    templates = make_templates(args.audit_dir, args.output, args.max_per_operator)
    print(f"Wrote {len(templates)} CEI template rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
