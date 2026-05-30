#!/usr/bin/env python3
"""Validate manually curated paired math CEI records."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from respondent_lab.counterfactual.cei_pairs import load_cei_pairs, validate_cei_pair  # noqa: E402


CEI_AUDIT_COLUMNS = [
    "cei_pair_id",
    "source_item_id",
    "source_certificate_id",
    "operator_id",
    "transform_type",
    "same_operator",
    "transformed_certificate_mev_v1",
    "answer_mapping_type",
    "answer_mapping_pass",
    "source_certificate_status",
    "cei_pair_pass",
    "notes",
]


def _csv_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fieldnames})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            json.dump(row, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")


def _load_source_certificate_lookup(audit_dir: Path) -> dict[str, dict[str, Any]] | None:
    audit_csv = audit_dir / "certificate_audit.csv"
    if not audit_csv.exists():
        return None
    with audit_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {str(row.get("certificate_id") or ""): row for row in rows if row.get("certificate_id")}


def _rate(rows: list[dict[str, Any]]) -> float:
    return sum(1 for row in rows if row.get("cei_pair_pass")) / len(rows) if rows else 0.0


def _grouped_rates(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "")].append(row)
    return {group_key: _rate(group_rows) for group_key, group_rows in sorted(grouped.items())}


def run_cei_pairs(audit_dir: Path, cei_pairs_path: Path, output_dir: Path) -> dict[str, Any]:
    pairs = load_cei_pairs(cei_pairs_path)
    source_lookup = _load_source_certificate_lookup(audit_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audit_rows = [validate_cei_pair(pair, source_lookup) for pair in pairs]
    failures = [row for row in audit_rows if not row.get("cei_pair_pass")]
    transformed_mev_values = [
        float(row["transformed_certificate_mev_v1"])
        for row in audit_rows
        if row.get("transformed_certificate_mev_v1") is not None
    ]

    transform_counts = Counter(str(row.get("transform_type") or "") for row in audit_rows)
    operator_counts = Counter(str(row.get("operator_id") or "") for row in audit_rows)
    summary = {
        "total_cei_pairs": len(audit_rows),
        "cei_pairs_by_transform_type": dict(sorted(transform_counts.items())),
        "cei_pairs_by_operator": dict(sorted(operator_counts.items())),
        "cei_pass_rate_overall": _rate(audit_rows),
        "cei_pass_rate_by_transform_type": _grouped_rates(audit_rows, "transform_type"),
        "cei_pass_rate_by_operator": _grouped_rates(audit_rows, "operator_id"),
        "source_certificate_checked_count": sum(
            1 for row in audit_rows if row.get("source_certificate_status") in {"passed", "failed"}
        ),
        "source_certificate_missing_count": sum(
            1 for row in audit_rows if row.get("source_certificate_status") == "missing"
        ),
        "transformed_certificate_mev_v1_mean": (
            sum(transformed_mev_values) / len(transformed_mev_values) if transformed_mev_values else 0.0
        ),
    }

    _write_csv(output_dir / "cei_pair_audit.csv", CEI_AUDIT_COLUMNS, audit_rows)
    _write_json(output_dir / "cei_summary.json", summary)
    _write_jsonl(output_dir / "cei_failures.jsonl", failures)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", required=True, type=Path)
    parser.add_argument("--cei-pairs", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    try:
        summary = run_cei_pairs(args.audit_dir, args.cei_pairs, args.output_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
