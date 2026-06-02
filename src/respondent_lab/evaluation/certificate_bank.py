"""Certificate-bank construction for Baseline Evaluator v0."""

from __future__ import annotations

import copy
import csv
import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from respondent_lab.io.normalization import normalize_answer_object


CERTIFICATE_BANK_FIELDS = [
    "item_id",
    "certificate_id",
    "candidate_answer",
    "normalized_answer_type",
    "operator_ids",
    "operator_signature",
    "mev_v1",
    "cei_score",
    "cei_pair_count",
    "mdv_v1",
    "validation_scope",
    "cei_status",
    "metadata",
]

_BOOL_FIELDS = {
    "answer_mapping_pass",
    "answer_match",
    "derived_answer_present",
    "gate_answer_match",
    "gate_candidate_present",
    "gate_incorrectness",
    "gate_operator_match",
    "gate_trace_executable",
    "gate_wrong_trace_present",
    "has_candidate_answer",
    "has_wrong_trace",
    "incorrectness",
    "is_composite",
    "operator_match",
    "parse_failure",
    "same_operator",
    "trace_executable_lite",
    "cei_pair_pass",
}

_FLOAT_FIELDS = {
    "locality_score",
    "mev_lite",
    "mev_v1",
    "transformed_certificate_mev_v1",
}


def load_certificate_audit(path: str | Path) -> list[dict[str, Any]]:
    """Load and normalize a certificate audit CSV."""

    rows = _read_csv(path)
    return [_prepare_certificate_row(row, row_number=index) for index, row in enumerate(rows, start=2)]


def load_cei_pair_audit(path: str | Path | None) -> list[dict[str, Any]]:
    """Load a CEI pair audit CSV, returning an empty list when the path is absent."""

    if path is None:
        return []
    audit_path = Path(path)
    if not audit_path.exists():
        return []
    rows = _read_csv(audit_path)
    return [_prepare_cei_row(row) for row in rows]


def build_certificate_bank(
    certificate_audit_csv: str | Path | Sequence[dict[str, Any]],
    cei_pair_audit_csv: str | Path | Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build validated single-operator certificate-bank records."""

    certificate_rows = _coerce_certificate_rows(certificate_audit_csv)
    cei_missing = _cei_source_missing(cei_pair_audit_csv)
    cei_rows = _coerce_cei_rows(cei_pair_audit_csv)
    cei_by_certificate = _aggregate_cei_pairs(cei_rows)

    bank: list[dict[str, Any]] = []
    for row in certificate_rows:
        if not _eligible_certificate_row(row):
            continue

        operator_ids = [str(operator_id) for operator_id in row.get("applied_operator_ids") or []]
        candidate_answer = normalize_answer_object(row["candidate_answer"])
        mev_v1 = _as_float(row.get("mev_v1"))
        if mev_v1 is None and str(row.get("mev_status") or "") == "validated":
            mev_v1 = 1.0

        cei = cei_by_certificate.get(str(row.get("certificate_id") or ""))
        if cei_missing:
            cei_score = None
            cei_pair_count = 0
            cei_status = "missing"
        elif cei is None:
            cei_score = None
            cei_pair_count = 0
            cei_status = "not_covered"
        else:
            cei_score = cei["cei_score"]
            cei_pair_count = cei["cei_pair_count"]
            cei_status = _cei_status(cei_score)

        mdv_v1 = mev_v1 * cei_score if mev_v1 is not None and cei_score is not None else None
        bank.append(
            {
                "item_id": str(row.get("item_id") or ""),
                "certificate_id": str(row.get("certificate_id") or ""),
                "candidate_answer": candidate_answer,
                "normalized_answer_type": str(candidate_answer.get("type") or ""),
                "operator_ids": operator_ids,
                "operator_signature": "+".join(operator_ids),
                "mev_v1": mev_v1,
                "cei_score": cei_score,
                "cei_pair_count": cei_pair_count,
                "mdv_v1": mdv_v1,
                "validation_scope": "single_operator_single_divergence",
                "cei_status": cei_status,
                "metadata": {
                    "parse_failure": bool(row.get("parse_failure")),
                    "audit_notes": str(row.get("notes") or ""),
                },
            }
        )

    return sorted(bank, key=lambda item: (item["item_id"], item["certificate_id"]))


def write_certificate_bank(bank: Sequence[dict[str, Any]], output_path: str | Path) -> None:
    """Write certificate-bank records as JSON, JSONL, or CSV based on the suffix."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [copy.deepcopy(record) for record in bank]

    if path.suffix.lower() == ".json":
        with path.open("w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        return

    if path.suffix.lower() == ".csv":
        fieldnames = _fieldnames(records)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow({key: _csv_cell(record.get(key)) for key in fieldnames})
        return

    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")


def _read_csv(path: str | Path) -> list[dict[str, Any]]:
    audit_path = Path(path)
    if not audit_path.exists():
        raise FileNotFoundError(audit_path)
    with audit_path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _prepare_certificate_row(row: dict[str, Any], *, row_number: int | None = None) -> dict[str, Any]:
    prepared = _prepare_common_row(row)
    try:
        prepared["applied_operator_ids"] = _parse_operator_ids(prepared.get("applied_operator_ids"))
        candidate_answer = _parse_json_cell(prepared.get("candidate_answer"), default=None)
    except ValueError as exc:
        location = f" on CSV row {row_number}" if row_number is not None else ""
        raise ValueError(f"Invalid certificate audit JSON{location}: {exc}") from exc

    if isinstance(candidate_answer, dict):
        prepared["candidate_answer"] = normalize_answer_object(candidate_answer)
    else:
        prepared["candidate_answer"] = candidate_answer
    return prepared


def _prepare_cei_row(row: dict[str, Any]) -> dict[str, Any]:
    return _prepare_common_row(row)


def _prepare_common_row(row: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(row)
    for field in _BOOL_FIELDS:
        if field in prepared:
            prepared[field] = _parse_bool(prepared.get(field))
    for field in _FLOAT_FIELDS:
        if field in prepared:
            prepared[field] = _as_float(prepared.get(field))
    return prepared


def _coerce_certificate_rows(source: str | Path | Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(source, (str, Path)):
        return load_certificate_audit(source)
    return [_prepare_certificate_row(dict(row)) for row in source]


def _coerce_cei_rows(source: str | Path | Sequence[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if source is None:
        return []
    if isinstance(source, (str, Path)):
        return load_cei_pair_audit(source)
    return [_prepare_cei_row(dict(row)) for row in source]


def _cei_source_missing(source: str | Path | Sequence[dict[str, Any]] | None) -> bool:
    if source is None:
        return True
    if isinstance(source, (str, Path)):
        return not Path(source).exists()
    return False


def _eligible_certificate_row(row: dict[str, Any]) -> bool:
    if str(row.get("validation_status") or "") != "validated":
        return False
    if _parse_bool(row.get("is_composite")) is True:
        return False

    operator_ids = [operator_id for operator_id in row.get("applied_operator_ids") or [] if operator_id]
    if len(operator_ids) != 1:
        return False

    mev_v1 = _as_float(row.get("mev_v1"))
    if str(row.get("mev_status") or "") != "validated" and mev_v1 != 1.0:
        return False

    candidate_answer = row.get("candidate_answer")
    return isinstance(candidate_answer, dict) and _value_present(candidate_answer.get("value"))


def _aggregate_cei_pairs(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source_certificate_id = str(row.get("source_certificate_id") or "")
        if source_certificate_id:
            grouped[source_certificate_id].append(row)

    aggregates: dict[str, dict[str, Any]] = {}
    for certificate_id, group in grouped.items():
        total_count = len(group)
        pass_count = sum(1 for row in group if _parse_bool(row.get("cei_pair_pass")) is True)
        aggregates[certificate_id] = {
            "cei_score": pass_count / total_count if total_count else None,
            "cei_pair_count": total_count,
            "cei_pass_count": pass_count,
        }
    return aggregates


def _cei_status(score: float | None) -> str:
    if score is None:
        return "not_covered"
    if score == 1.0:
        return "passed"
    if score == 0.0:
        return "failed"
    return "partial"


def _parse_operator_ids(value: Any) -> list[str]:
    parsed = _parse_json_cell(value, default=[])
    if parsed is None:
        return []
    if isinstance(parsed, str):
        return [parsed] if parsed else []
    if isinstance(parsed, list):
        return [str(operator_id) for operator_id in parsed if operator_id]
    raise ValueError("applied_operator_ids must be a JSON list")


def _parse_json_cell(value: Any, *, default: Any) -> Any:
    if value is None or value == "":
        return copy.deepcopy(default)
    if isinstance(value, (dict, list)):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        return copy.deepcopy(value)
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc


def _parse_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _value_present(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _fieldnames(records: Sequence[dict[str, Any]]) -> list[str]:
    extras = sorted({key for record in records for key in record if key not in CERTIFICATE_BANK_FIELDS})
    return [*CERTIFICATE_BANK_FIELDS, *extras]


def _csv_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value
