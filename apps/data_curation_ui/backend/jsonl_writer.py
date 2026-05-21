from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import OutputConfigResponse
from path_security import display_path, safe_existing_or_new_jsonl


class JsonlWriterError(RuntimeError):
    pass


class JsonlWriter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.log_path = repo_root / ".dg_curation" / "append_log.jsonl"

    def status(self, output_path: str) -> OutputConfigResponse:
        path = safe_existing_or_new_jsonl(output_path, self.repo_root)
        item_count, last_item_id = self._scan_status(path)
        return OutputConfigResponse(
            output_path=display_path(path, self.repo_root),
            exists=path.exists(),
            item_count=item_count,
            last_item_id=last_item_id,
        )

    def has_item_id(self, path: Path, item_id: str) -> bool:
        if not path.exists():
            return False
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise JsonlWriterError(
                        f"Existing JSONL contains invalid JSON at line {line_number}: {exc}"
                    ) from exc
                if payload.get("item_id") == item_id:
                    return True
        return False

    def append(
        self,
        output_path: str,
        item: dict[str, Any],
        *,
        workspace_id: str | None,
        source_dataset_id: str | None,
        source_record_index: int | None,
    ) -> int:
        path = safe_existing_or_new_jsonl(output_path, self.repo_root)
        item_id = str(item.get("item_id", "")).strip()
        if not item_id:
            raise JsonlWriterError("item_id is required before append.")
        if self.has_item_id(path, item_id):
            raise JsonlWriterError(f"Duplicate item_id in output file: {item_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._append_log(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "workspace_id": workspace_id,
                "output_path": display_path(path, self.repo_root),
                "item_id": item_id,
                "source_dataset_id": source_dataset_id,
                "source_record_index": source_record_index,
            }
        )
        item_count, _ = self._scan_status(path)
        return item_count

    def _scan_status(self, path: Path) -> tuple[int, str | None]:
        if not path.exists():
            return 0, None
        item_count = 0
        last_item_id: str | None = None
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise JsonlWriterError(
                        f"Existing JSONL contains invalid JSON at line {line_number}: {exc}"
                    ) from exc
                item_count += 1
                last_item_id = payload.get("item_id")
        return item_count, last_item_id

    def _append_log(self, payload: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

