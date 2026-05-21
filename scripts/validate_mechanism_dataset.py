#!/usr/bin/env python3
"""Validate a manually prepared mechanism-only dataset JSONL file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from respondent_lab.audit.leakage_guard import LeakageError, assert_no_leakage_payload  # noqa: E402
from respondent_lab.mechanisms.operator_registry import register_default_operators  # noqa: E402
from respondent_lab.schemas.items import Item  # noqa: E402

MISSING_DATA_MESSAGE = (
    "Data file not found. Manual data preparation is required. "
    "See data/README_manual_data_prep.md."
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def validate_dataset(input_path: Path, config_path: Path, out_path: Path) -> tuple[int, dict[str, Any]]:
    if not input_path.exists():
        print(MISSING_DATA_MESSAGE, file=sys.stderr)
        return 1, {}

    config = _load_yaml(config_path)
    forbidden_keys = set(config.get("forbidden_fields") or [])
    schema = _load_json(ROOT / "schemas" / "item_schema.json")
    register_default_operators()

    report: dict[str, Any] = {
        "n_items": 0,
        "schema_pass": 0,
        "leakage_pass": 0,
        "failed_items": [],
        "operator_coverage": {},
    }

    with input_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            report["n_items"] += 1
            item_id = f"line:{line_number}"
            try:
                payload = json.loads(text)
                item_id = payload.get("item_id", item_id)
            except json.JSONDecodeError as exc:
                report["failed_items"].append(
                    {"line": line_number, "item_id": item_id, "stage": "json", "error": str(exc)}
                )
                continue

            try:
                jsonschema.validate(instance=payload, schema=schema)
                report["schema_pass"] += 1
            except Exception as exc:  # noqa: BLE001
                report["failed_items"].append(
                    {"line": line_number, "item_id": item_id, "stage": "schema", "error": str(exc)}
                )
                continue

            try:
                assert_no_leakage_payload(payload, forbidden_keys or None)
                report["leakage_pass"] += 1
            except LeakageError as exc:
                report["failed_items"].append(
                    {"line": line_number, "item_id": item_id, "stage": "leakage", "error": str(exc)}
                )
                continue

            try:
                item = Item.model_validate(payload)
            except Exception as exc:  # noqa: BLE001
                report["failed_items"].append(
                    {"line": line_number, "item_id": item_id, "stage": "item", "error": str(exc)}
                )
                continue

            for operator_id in item.allowed_operator_ids:
                coverage = report["operator_coverage"]
                coverage[operator_id] = coverage.get(operator_id, 0) + 1

    report["operator_coverage"] = dict(sorted(report["operator_coverage"].items()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return (0 if not report["failed_items"] else 1), report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    exit_code, _ = validate_dataset(args.input, args.config, args.out)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
