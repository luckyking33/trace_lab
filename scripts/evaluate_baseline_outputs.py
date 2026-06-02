#!/usr/bin/env python3
"""Evaluate deterministic baseline outputs against certificate-bank answers."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from respondent_lab.evaluation.baseline_evaluator import evaluate_generated_item  # noqa: E402
from respondent_lab.evaluation.certificate_bank import build_certificate_bank  # noqa: E402
from respondent_lab.evaluation.generated_outputs import load_generated_outputs  # noqa: E402
from respondent_lab.io.math_dataset_loader import load_and_normalize_math_items  # noqa: E402


CANDIDATE_EVAL_COLUMNS = [
    "run_id",
    "method",
    "item_id",
    "candidate_id",
    "raw_answer",
    "normalized_answer",
    "parse_success",
    "incorrectness",
    "duplicate_within_slate",
    "known_certificate_match",
    "matched_certificate_id",
    "matched_operator_ids",
    "matched_mev_v1",
    "matched_cei_score",
    "matched_mdv_v1",
    "self_certificate_present",
    "self_mev_v1",
    "final_certification_status",
    "notes",
]

SLATE_EVAL_COLUMNS = [
    "run_id",
    "method",
    "item_id",
    "num_candidates",
    "parse_success_count",
    "incorrect_count",
    "unique_answer_count",
    "duplicate_answer_count",
    "known_certified_count",
    "self_certified_count",
    "certified_operator_ids",
    "operator_coverage",
    "answer_redundancy",
    "operator_redundancy",
    "mean_pairwise_signature_distance",
    "mean_mdv_v1_certified_only",
    "slate_mdv_v1_lite",
    "mdv_status",
    "notes",
]

INVALID_STATUSES = {
    "invalid_parse_failure",
    "invalid_equivalent_to_correct",
    "invalid_duplicate",
}


def run_evaluation(
    *,
    items: Path,
    certificate_audit: Path,
    cei_audit: Path | None,
    generated: Path,
    output_dir: Path,
) -> dict[str, Any]:
    item_records = load_and_normalize_math_items(items)
    items_by_id = {str(record.get("item_id") or ""): record for record in item_records}
    certificate_bank = build_certificate_bank(certificate_audit, cei_audit)
    bank_by_item = _group_by_item_id(certificate_bank)
    generated_outputs = load_generated_outputs(generated)
    overall_cei_status = _overall_cei_status(cei_audit, certificate_bank)

    output_dir.mkdir(parents=True, exist_ok=True)

    candidate_rows: list[dict[str, Any]] = []
    slate_rows: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    invalid_candidates: list[dict[str, Any]] = []

    default_method = generated.stem
    for generated_output in generated_outputs:
        generated_item = _plain(generated_output)
        item_id = str(generated_item.get("item_id") or "")
        if item_id not in items_by_id:
            raise ValueError(f"Generated output references unknown item_id: {item_id}")

        method = str(generated_item.get("method") or default_method)
        run_id = str(generated_item.get("run_id") or method)
        bank_for_item = bank_by_item.get(item_id, [])
        result = evaluate_generated_item(items_by_id[item_id], generated_output, bank_for_item)

        for record in result.get("candidate_evaluations") or []:
            candidate_record = _plain(record)
            notes = _candidate_notes(candidate_record, overall_cei_status)
            row = _candidate_csv_row(
                run_id=run_id,
                method=method,
                item_id=item_id,
                candidate_record=candidate_record,
                notes=notes,
            )
            candidate_rows.append(row)

            queue_payload = {**row, "notes": notes}
            if _is_review_queue_candidate(candidate_record):
                review_queue.append({**queue_payload, "queue_reason": "incorrect_unmatched"})
            if str(candidate_record.get("final_certification_status") or "") in INVALID_STATUSES:
                invalid_candidates.append(
                    {
                        **queue_payload,
                        "invalid_reason": candidate_record.get("final_certification_status"),
                    }
                )

        slate_metrics = _plain(result.get("slate_metrics") or {})
        slate_notes = _notes(slate_metrics.get("notes"))
        if overall_cei_status == "missing":
            _add_note(slate_notes, "cei_status=missing")
        slate_rows.append(
            _slate_csv_row(
                run_id=run_id,
                method=method,
                item_id=item_id,
                slate_metrics=slate_metrics,
                notes=slate_notes,
            )
        )

    summary = _method_summary(
        candidate_rows=candidate_rows,
        slate_rows=slate_rows,
        review_queue_count=len(review_queue),
        invalid_candidate_count=len(invalid_candidates),
        cei_status=overall_cei_status,
    )

    _write_csv(output_dir / "candidate_eval.csv", CANDIDATE_EVAL_COLUMNS, candidate_rows)
    _write_csv(output_dir / "slate_eval.csv", SLATE_EVAL_COLUMNS, slate_rows)
    _write_json(output_dir / "method_summary.json", summary)
    _write_jsonl(output_dir / "review_queue.jsonl", review_queue)
    _write_jsonl(output_dir / "invalid_candidates.jsonl", invalid_candidates)
    return summary


def _group_by_item_id(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("item_id") or "")].append(record)
    return dict(grouped)


def _overall_cei_status(cei_audit: Path | None, certificate_bank: list[dict[str, Any]]) -> str:
    if cei_audit is None or not Path(cei_audit).exists():
        return "missing"
    statuses = Counter(str(record.get("cei_status") or "unknown") for record in certificate_bank)
    if not statuses:
        return "no_certificate_bank"
    if set(statuses) == {"passed"}:
        return "passed"
    if any(status in statuses for status in ("failed", "partial")):
        return "has_failures"
    if "not_covered" in statuses and "passed" in statuses:
        return "partial_coverage"
    if "not_covered" in statuses:
        return "not_covered"
    return ",".join(sorted(statuses))


def _candidate_notes(candidate_record: dict[str, Any], overall_cei_status: str) -> list[str]:
    notes = _notes(candidate_record.get("notes"))
    if candidate_record.get("known_certificate_match"):
        matched_cei_status = candidate_record.get("matched_cei_status")
        if matched_cei_status:
            _add_note(notes, f"matched_cei_status={matched_cei_status}")
        elif overall_cei_status == "missing":
            _add_note(notes, "matched_cei_status=missing")
    elif overall_cei_status == "missing":
        _add_note(notes, "cei_status=missing")
    return notes


def _candidate_csv_row(
    *,
    run_id: str,
    method: str,
    item_id: str,
    candidate_record: dict[str, Any],
    notes: list[str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "method": method,
        "item_id": item_id,
        "candidate_id": candidate_record.get("candidate_id"),
        "raw_answer": candidate_record.get("raw_answer"),
        "normalized_answer": candidate_record.get("normalized_answer"),
        "parse_success": candidate_record.get("parse_success"),
        "incorrectness": candidate_record.get("incorrectness"),
        "duplicate_within_slate": candidate_record.get("duplicate_within_slate"),
        "known_certificate_match": candidate_record.get("known_certificate_match"),
        "matched_certificate_id": candidate_record.get("matched_certificate_id"),
        "matched_operator_ids": candidate_record.get("matched_operator_ids"),
        "matched_mev_v1": candidate_record.get("matched_mev_v1"),
        "matched_cei_score": candidate_record.get("matched_cei_score"),
        "matched_mdv_v1": candidate_record.get("matched_mdv_v1"),
        "self_certificate_present": candidate_record.get("self_certificate_present"),
        "self_mev_v1": candidate_record.get("self_mev_v1"),
        "final_certification_status": candidate_record.get("final_certification_status"),
        "notes": notes,
    }


def _slate_csv_row(
    *,
    run_id: str,
    method: str,
    item_id: str,
    slate_metrics: dict[str, Any],
    notes: list[str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "method": method,
        "item_id": item_id,
        "num_candidates": slate_metrics.get("num_candidates"),
        "parse_success_count": slate_metrics.get("parse_success_count"),
        "incorrect_count": slate_metrics.get("incorrect_count"),
        "unique_answer_count": slate_metrics.get("unique_answer_count"),
        "duplicate_answer_count": slate_metrics.get("duplicate_answer_count"),
        "known_certified_count": slate_metrics.get("known_certified_count"),
        "self_certified_count": slate_metrics.get("self_certified_count"),
        "certified_operator_ids": slate_metrics.get("certified_operator_ids"),
        "operator_coverage": slate_metrics.get("operator_coverage"),
        "answer_redundancy": slate_metrics.get("answer_redundancy"),
        "operator_redundancy": slate_metrics.get("operator_redundancy"),
        "mean_pairwise_signature_distance": slate_metrics.get("mean_pairwise_signature_distance"),
        "mean_mdv_v1_certified_only": slate_metrics.get("mean_mdv_v1_certified_only"),
        "slate_mdv_v1_lite": slate_metrics.get("slate_mdv_v1_lite"),
        "mdv_status": slate_metrics.get("mdv_status"),
        "notes": notes,
    }


def _method_summary(
    *,
    candidate_rows: list[dict[str, Any]],
    slate_rows: list[dict[str, Any]],
    review_queue_count: int,
    invalid_candidate_count: int,
    cei_status: str,
) -> dict[str, Any]:
    num_candidates = len(candidate_rows)
    methods = sorted({str(row.get("method") or "") for row in candidate_rows if row.get("method")})
    run_ids = sorted({str(row.get("run_id") or "") for row in candidate_rows if row.get("run_id")})
    unique_candidate_count = sum(1 for row in candidate_rows if row.get("parse_success") and not row.get("duplicate_within_slate"))
    return {
        "run_id": run_ids[0] if len(run_ids) == 1 else ("mixed" if run_ids else ""),
        "method": methods[0] if len(methods) == 1 else ("mixed" if methods else ""),
        "num_items": len(slate_rows),
        "num_candidates": num_candidates,
        "parse_success_rate": _rate(sum(1 for row in candidate_rows if row.get("parse_success")), num_candidates),
        "incorrectness_rate": _rate(sum(1 for row in candidate_rows if row.get("incorrectness") is True), num_candidates),
        "unique_answer_rate": _rate(unique_candidate_count, num_candidates),
        "known_certificate_match_rate": _rate(
            sum(1 for row in candidate_rows if row.get("known_certificate_match")), num_candidates
        ),
        "self_certificate_rate": _rate(
            sum(1 for row in candidate_rows if row.get("self_certificate_present")), num_candidates
        ),
        "self_mev_v1_mean": _mean(_float_values(row.get("self_mev_v1") for row in candidate_rows)),
        "matched_mev_v1_mean": _mean(_float_values(row.get("matched_mev_v1") for row in candidate_rows)),
        "matched_cei_score_mean": _mean(_float_values(row.get("matched_cei_score") for row in candidate_rows)),
        "matched_mdv_v1_mean": _mean(_float_values(row.get("matched_mdv_v1") for row in candidate_rows)),
        "mean_operator_coverage": _mean(_float_values(row.get("operator_coverage") for row in slate_rows)),
        "mean_slate_mdv_v1_lite": _mean(_float_values(row.get("slate_mdv_v1_lite") for row in slate_rows)),
        "review_queue_count": review_queue_count,
        "invalid_candidate_count": invalid_candidate_count,
        "cei_status": cei_status,
    }


def _is_review_queue_candidate(candidate_record: dict[str, Any]) -> bool:
    if candidate_record.get("incorrectness") is not True:
        return False
    if candidate_record.get("known_certificate_match"):
        return False
    return _float_or_none(candidate_record.get("self_mev_v1")) != 1.0


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


def _csv_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: _plain(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _notes(value: Any) -> list[str]:
    value = _plain(value)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


def _add_note(notes: list[str], note: str) -> None:
    if note not in notes:
        notes.append(note)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _float_values(values: Any) -> list[float]:
    result: list[float] = []
    for value in values:
        parsed = _float_or_none(value)
        if parsed is not None:
            result.append(parsed)
    return result


def _float_or_none(value: Any) -> float | None:
    if value in (None, "", "None", "none", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", required=True, type=Path)
    parser.add_argument("--certificate-audit", required=True, type=Path)
    parser.add_argument("--cei-audit", type=Path)
    parser.add_argument("--generated", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    try:
        summary = run_evaluation(
            items=args.items,
            certificate_audit=args.certificate_audit,
            cei_audit=args.cei_audit,
            generated=args.generated,
            output_dir=args.output_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
