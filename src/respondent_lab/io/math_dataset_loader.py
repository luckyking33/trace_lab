"""JSONL loading and role splitting for the math certificate audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from respondent_lab.io.normalization import normalize_item_record


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL file as raw dictionaries."""

    data_path = Path(path)
    if not data_path.exists():
        raise FileNotFoundError(data_path)

    records: list[dict[str, Any]] = []
    with data_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object on line {line_number}")
            records.append(payload)
    return records


def load_and_normalize_math_items(path: str | Path) -> list[dict[str, Any]]:
    """Load JSONL records and normalize them without rejecting negative controls."""

    return [normalize_item_record(record) for record in load_jsonl(path)]


def split_by_item_role(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group records by item_role, preserving unknown roles as their own bucket."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        role = str(record.get("item_role") or "unknown")
        grouped.setdefault(role, []).append(record)
    return grouped
