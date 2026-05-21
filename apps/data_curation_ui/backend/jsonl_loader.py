from __future__ import annotations

import json
import hashlib
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from leakage_guard import record_leakage_warnings
from path_security import PathSecurityError, display_path, resolve_under_repo


class JsonlLoadError(RuntimeError):
    pass


class JsonlLoader:
    def __init__(self, repo_root: Path, forbidden_keys: set[str]) -> None:
        self.repo_root = repo_root
        self.forbidden_keys = forbidden_keys

    def meta(self, raw_path: str) -> dict[str, Any]:
        path = self._safe_jsonl_path(raw_path)
        fields: list[str] = []
        field_types: dict[str, str] = {}
        count = 0
        for record in self._iter_records(path):
            count += 1
            for key, value in record.items():
                if key not in field_types:
                    fields.append(key)
                    field_types[key] = self._type_label(value)
        return {
            "dataset_id": self.dataset_id(path),
            "path": display_path(path, self.repo_root),
            "format": "jsonl",
            "num_rows": count,
            "fields": fields,
            "field_types": field_types,
        }

    def record(self, raw_path: str, index: int) -> dict[str, Any]:
        if index < 0:
            raise IndexError("Record index must be non-negative.")
        path = self._safe_jsonl_path(raw_path)
        count = 0
        for count, record in enumerate(self._iter_records(path), start=1):
            zero_based = count - 1
            if zero_based == index:
                return {
                    "dataset_id": self.dataset_id(path),
                    "path": display_path(path, self.repo_root),
                    "index": index,
                    "num_rows": self.count(path),
                    "record": record,
                    "leakage_warnings": record_leakage_warnings(record, self.forbidden_keys),
                }
        raise IndexError(f"Record index out of range: {index}. JSONL has {count} rows.")

    def records(self, raw_path: str, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        if offset < 0:
            raise IndexError("Offset must be non-negative.")
        if limit < 1:
            raise IndexError("Limit must be positive.")
        path = self._safe_jsonl_path(raw_path)
        records: list[dict[str, Any]] = []
        count = 0
        for count, record in enumerate(self._iter_records(path), start=1):
            zero_based = count - 1
            if zero_based < offset:
                continue
            if len(records) >= limit:
                continue
            records.append(
                {
                    "index": zero_based,
                    "record": record,
                    "leakage_warnings": record_leakage_warnings(record, self.forbidden_keys),
                }
            )
        return {
            "dataset_id": self.dataset_id(path),
            "path": display_path(path, self.repo_root),
            "offset": offset,
            "limit": limit,
            "num_rows": count,
            "records": records,
        }

    def count(self, path: Path) -> int:
        return sum(1 for _ in self._iter_records(path))

    def dataset_id(self, path: Path) -> str:
        digest = hashlib.sha256(display_path(path, self.repo_root).encode("utf-8")).hexdigest()[:12]
        return f"jsonl_{digest}"

    def _safe_jsonl_path(self, raw_path: str) -> Path:
        path = resolve_under_repo(raw_path, self.repo_root, must_exist=True)
        if path.suffix.lower() != ".jsonl":
            raise PathSecurityError("JSONL viewer path must end with .jsonl.")
        if not path.is_file():
            raise PathSecurityError(f"JSONL viewer path is not a file: {display_path(path, self.repo_root)}")
        return path

    def _iter_records(self, path: Path) -> Iterator[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise JsonlLoadError(f"Invalid JSONL at line {line_number}: {exc.msg}") from exc
                if not isinstance(value, Mapping):
                    raise JsonlLoadError(f"Invalid JSONL at line {line_number}: each line must be an object.")
                yield dict(value)

    def _type_label(self, value: Any) -> str:
        if isinstance(value, list):
            return f"array[{len(value)}]"
        if value is None:
            return "null"
        return type(value).__name__
