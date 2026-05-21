from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class TranslationStore:
    def __init__(self, repo_root: Path) -> None:
        self.root = repo_root / ".dg_curation" / "translations"

    def load_field_translation(
        self, dataset_id: str, record_index: int, field_name: str, source_text: str
    ) -> dict[str, Any] | None:
        path = self._field_path(dataset_id, record_index, field_name, source_text)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_field_translation(
        self,
        dataset_id: str,
        record_index: int,
        field_name: str,
        source_text: str,
        translation_zh: str,
    ) -> dict[str, Any]:
        path = self._field_path(dataset_id, record_index, field_name, source_text)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dataset_id": dataset_id,
            "record_index": record_index,
            "field_name": field_name,
            "source_hash": self._hash(source_text),
            "translation_zh": translation_zh,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def load_metadata_translation(self, cache_key: str) -> dict[str, Any] | None:
        path = self.root / "metadata" / f"{self._safe(cache_key)}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_metadata_translation(self, cache_key: str, fields: dict[str, str]) -> dict[str, Any]:
        path = self.root / "metadata" / f"{self._safe(cache_key)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cache_key": cache_key, "fields": fields}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def metadata_cache_key(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return self._hash(serialized)

    def _field_path(self, dataset_id: str, record_index: int, field_name: str, source_text: str) -> Path:
        safe_dataset = self._safe(dataset_id)
        safe_field = self._safe(field_name)
        digest = self._hash(source_text)
        return self.root / "fields" / safe_dataset / f"{record_index}_{safe_field}_{digest}.json"

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def _safe(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", value)

