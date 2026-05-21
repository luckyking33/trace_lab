"""Load manually prepared mechanism-only JSONL items."""

from __future__ import annotations

import json
from pathlib import Path

from respondent_lab.schemas.items import Item


def load_items_jsonl(path: str | Path) -> list[Item]:
    data_path = Path(path)
    if not data_path.exists():
        raise FileNotFoundError(data_path)

    items: list[Item] = []
    with data_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            try:
                items.append(Item.model_validate(payload))
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Invalid item on line {line_number}: {exc}") from exc
    return items
