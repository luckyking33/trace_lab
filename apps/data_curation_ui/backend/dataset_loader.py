from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.ipc as ipc
from datasets import Dataset

from leakage_guard import record_leakage_warnings
from models import DatasetRecordResponse, DatasetRecordsResponse, DatasetSummary
from path_security import display_path, resolve_under_repo


class DatasetLoadError(RuntimeError):
    pass


@dataclass
class LoadedDatasetRef:
    dataset_id: str
    path: Path
    format: str
    num_rows: int
    fields: list[str]
    field_types: dict[str, str]
    backend: str
    dataset: Any


class DatasetRegistry:
    def __init__(self, repo_root: Path, forbidden_keys: set[str]) -> None:
        self.repo_root = repo_root
        self.forbidden_keys = forbidden_keys
        self._datasets: dict[str, LoadedDatasetRef] = {}

    def load(self, raw_path: str) -> LoadedDatasetRef:
        path = resolve_under_repo(raw_path, self.repo_root, must_exist=True)
        dataset_id = self._dataset_id(path)
        if dataset_id in self._datasets:
            return self._datasets[dataset_id]

        errors: list[str] = []
        try:
            ds = Dataset.from_file(str(path))
            fields = list(ds.column_names)
            field_types = {name: str(ds.features[name]) for name in fields}
            ref = LoadedDatasetRef(
                dataset_id=dataset_id,
                path=path,
                format="huggingface_arrow",
                num_rows=len(ds),
                fields=fields,
                field_types=field_types,
                backend="datasets",
                dataset=ds,
            )
            self._datasets[dataset_id] = ref
            return ref
        except Exception as exc:  # noqa: BLE001 - fallback needs clear aggregate errors
            errors.append(f"datasets.Dataset.from_file failed: {exc}")

        for opener_name, opener in (("arrow_file", ipc.open_file), ("arrow_stream", ipc.open_stream)):
            try:
                with pa.memory_map(str(path), "r") as source:
                    reader = opener(source)
                    table = reader.read_all()
                fields = list(table.column_names)
                field_types = {field.name: str(field.type) for field in table.schema}
                ref = LoadedDatasetRef(
                    dataset_id=dataset_id,
                    path=path,
                    format=opener_name,
                    num_rows=table.num_rows,
                    fields=fields,
                    field_types=field_types,
                    backend="pyarrow",
                    dataset=table,
                )
                self._datasets[dataset_id] = ref
                return ref
            except Exception as exc:  # noqa: BLE001
                errors.append(f"pyarrow.ipc.{opener_name} failed: {exc}")

        raise DatasetLoadError("Unsupported dataset file. " + " | ".join(errors))

    def meta(self, dataset_id: str) -> DatasetSummary:
        ref = self._get(dataset_id)
        return self._summary(ref)

    def record(self, dataset_id: str, index: int) -> DatasetRecordResponse:
        ref = self._get(dataset_id)
        if index < 0 or index >= ref.num_rows:
            raise IndexError(f"Record index out of range: {index}. Valid range is 0..{ref.num_rows - 1}.")
        record = self._row(ref, index)
        return DatasetRecordResponse(
            dataset_id=dataset_id,
            index=index,
            num_rows=ref.num_rows,
            record=record,
            leakage_warnings=record_leakage_warnings(record, self.forbidden_keys),
        )

    def records(self, dataset_id: str, offset: int, limit: int) -> DatasetRecordsResponse:
        ref = self._get(dataset_id)
        safe_offset = max(0, offset)
        safe_limit = max(1, min(limit, 100))
        end = min(ref.num_rows, safe_offset + safe_limit)
        records = [self._row(ref, index) for index in range(safe_offset, end)]
        return DatasetRecordsResponse(
            dataset_id=dataset_id,
            offset=safe_offset,
            limit=safe_limit,
            num_rows=ref.num_rows,
            records=records,
        )

    def _get(self, dataset_id: str) -> LoadedDatasetRef:
        try:
            return self._datasets[dataset_id]
        except KeyError as exc:
            raise KeyError(f"Dataset is not loaded in this backend session: {dataset_id}") from exc

    def _summary(self, ref: LoadedDatasetRef) -> DatasetSummary:
        return DatasetSummary(
            dataset_id=ref.dataset_id,
            path=display_path(ref.path, self.repo_root),
            format=ref.format,
            num_rows=ref.num_rows,
            fields=ref.fields,
            field_types=ref.field_types,
        )

    def _row(self, ref: LoadedDatasetRef, index: int) -> dict[str, Any]:
        if ref.backend == "datasets":
            row = ref.dataset[int(index)]
            return dict(row)
        table = ref.dataset.slice(index, 1)
        rows = table.to_pylist()
        return dict(rows[0]) if rows else {}

    def _dataset_id(self, path: Path) -> str:
        rel = display_path(path, self.repo_root)
        digest = hashlib.sha1(f"{rel}:{path.stat().st_size}".encode("utf-8")).hexdigest()[:12]
        return f"ds_{digest}"

    def summary_from_ref(self, ref: LoadedDatasetRef) -> DatasetSummary:
        return self._summary(ref)

