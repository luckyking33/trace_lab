#!/usr/bin/env python3
"""Run the deterministic Math Certificate Audit v0."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from respondent_lab.audit.leakage_guard import build_leakage_audit  # noqa: E402
from respondent_lab.certificates.extraction import extract_certificates  # noqa: E402
from respondent_lab.certificates.validation import validate_certificate  # noqa: E402
from respondent_lab.io.math_dataset_loader import load_and_normalize_math_items  # noqa: E402
from respondent_lab.mechanisms.operator_registry import (  # noqa: E402
    get_applicable_operators,
    register_default_operators,
)
from respondent_lab.metrics.mechanism_dv import cei_readiness, compute_slate_mdv_lite  # noqa: E402
from respondent_lab.metrics.mechanistic_validity import compute_mev_lite, compute_mev_v1  # noqa: E402
from respondent_lab.schemas.items import Item  # noqa: E402


ITEM_AUDIT_COLUMNS = [
    "item_id",
    "item_role",
    "domain",
    "raw_answer_type",
    "normalized_answer_type",
    "allowed_operator_ids",
    "target_error_operator_id",
    "target_error_operator_ids",
    "negative_control_for_operator_id",
    "num_certificates",
    "leakage_pass",
    "schema_compatible",
    "cei_readiness",
    "notes",
]

CERTIFICATE_AUDIT_COLUMNS = [
    "item_id",
    "certificate_id",
    "item_role",
    "applied_operator_ids",
    "candidate_answer",
    "is_composite",
    "validation_status",
    "failure_type",
    "deferred_reason",
    "has_candidate_answer",
    "has_wrong_trace",
    "divergence_step_count",
    "operator_match",
    "derived_answer_present",
    "answer_match",
    "incorrectness",
    "trace_executable_lite",
    "parse_failure",
    "mev_lite",
    "mev_status",
    "mev_v1",
    "gate_candidate_present",
    "gate_wrong_trace_present",
    "gate_incorrectness",
    "gate_operator_match",
    "gate_answer_match",
    "gate_trace_executable",
    "locality_score",
    "notes",
]

SLATE_AUDIT_COLUMNS = [
    "item_id",
    "num_distractors",
    "allowed_operator_ids",
    "covered_operator_ids",
    "operator_coverage",
    "redundancy",
    "mean_pairwise_signature_distance",
    "mean_candidate_mev_lite",
    "slate_mdv_lite",
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


def _leakage_pass(record: dict[str, Any]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    flags = record.get("leakage_flags") or {}
    required_flags = [
        "original_distractors_removed",
        "human_response_dist_removed",
        "seed_candidates_removed",
    ]
    for flag in required_flags:
        if flags.get(flag) is not True:
            notes.append(f"leakage_flags.{flag} is not true")
    audit = build_leakage_audit(record)
    if not audit["forbidden_key_scan_passed"]:
        notes.append(f"forbidden key matches: {audit['forbidden_matches']}")
    if not audit["canary_scan_passed"]:
        notes.append(f"canary matches: {audit['canary_matches']}")
    return not notes, notes


def _light_negative_schema(record: dict[str, Any]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    for key in ["item_id", "subject", "domain", "question", "correct_answer", "solution_trace"]:
        if key not in record:
            notes.append(f"missing {key}")
    if record.get("subject") != "math":
        notes.append("subject is not math")
    if not isinstance(record.get("solution_trace"), list) or len(record.get("solution_trace") or []) < 2:
        notes.append("solution_trace has fewer than 2 steps")
    correct_answer = record.get("correct_answer") or {}
    if not isinstance(correct_answer, dict) or correct_answer.get("value") in (None, "", []):
        notes.append("correct_answer.value is empty")
    return not notes, notes


def _schema_compatible(record: dict[str, Any]) -> tuple[bool, list[str]]:
    if record.get("item_role") == "operator_unit_negative":
        return _light_negative_schema(record)
    try:
        Item.model_validate(record)
        return True, []
    except Exception as exc:  # noqa: BLE001 - report schema incompatibility.
        return False, [str(exc)]


def _applicable_operator_ids(record: dict[str, Any], allowed_override: list[str] | None = None) -> tuple[list[str], str | None]:
    payload = copy.deepcopy(record)
    if allowed_override is not None:
        payload["allowed_operator_ids"] = allowed_override
    try:
        item = Item.model_validate(payload)
        return [operator.operator_id for operator in get_applicable_operators(item)], None
    except Exception as exc:  # noqa: BLE001 - report audit incompatibility.
        return [], str(exc)


def _expected_positive_operator_ids(record: dict[str, Any]) -> list[str]:
    if record.get("target_error_operator_id"):
        return [str(record["target_error_operator_id"])]
    return [str(operator_id) for operator_id in record.get("target_error_operator_ids") or [] if operator_id]


def _operator_signature(certificate: dict[str, Any]) -> str:
    return "+".join(certificate.get("applied_operator_ids") or []) or "<none>"


def _certificate_deferred_reason(validation: dict[str, Any]) -> str:
    if validation.get("composite_deferred") or validation.get("composite_certificate") or validation.get("is_composite"):
        return "composite_certificate_deferred_in_v0"
    if validation.get("deferred"):
        return str(validation.get("deferred_reason") or "certificate_deferred")
    return ""


def _certificate_failure_type(validation: dict[str, Any]) -> str:
    if validation.get("mev_status") != "failed":
        return ""
    failed_gates = [
        key.removeprefix("gate_")
        for key in [
            "gate_candidate_present",
            "gate_wrong_trace_present",
            "gate_incorrectness",
            "gate_operator_match",
            "gate_answer_match",
            "gate_trace_executable",
        ]
        if not validation.get(key)
    ]
    if validation.get("locality_score") == 0.0:
        failed_gates.append("locality")
    return "mev_v1_gate_failure:" + ",".join(failed_gates or ["unknown"])


def run_audit(input_path: Path, output_dir: Path) -> dict[str, Any]:
    register_default_operators()
    records = load_and_normalize_math_items(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    item_rows: list[dict[str, Any]] = []
    certificate_rows: list[dict[str, Any]] = []
    slate_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    role_counts = Counter(str(record.get("item_role") or "unknown") for record in records)
    domain_counts = Counter(str(record.get("domain") or "unknown") for record in records)
    raw_answer_type_counts = Counter(str(record.get("_audit", {}).get("raw_answer_type") or "") for record in records)
    normalized_answer_type_counts = Counter(str(record.get("answer_type") or "") for record in records)

    all_certificates: list[dict[str, Any]] = []
    all_certificate_scores: list[float] = []
    single_operator_certificate_scores: list[float] = []
    validated_single_operator_certificates = 0
    composite_deferred_count = 0
    leakage_passes = 0
    positive_expected = 0
    positive_hits = 0
    negative_expected = 0
    negative_false_positives = 0

    for record in records:
        item_id = str(record.get("item_id") or "")
        item_notes: list[str] = []

        leakage_ok, leakage_notes = _leakage_pass(record)
        schema_ok, schema_notes = _schema_compatible(record)
        if leakage_ok:
            leakage_passes += 1
        item_notes.extend(leakage_notes)
        item_notes.extend(f"schema: {note}" for note in schema_notes)

        expected_positive_ids = _expected_positive_operator_ids(record)
        if record.get("item_role") == "operator_unit_negative":
            negative_operator_id = record.get("negative_control_for_operator_id")
            if negative_operator_id:
                negative_expected += 1
                applicable_ids, error = _applicable_operator_ids(record, [str(negative_operator_id)])
                if error:
                    item_notes.append(f"negative precondition audit unavailable: {error}")
                if negative_operator_id in applicable_ids:
                    negative_false_positives += 1
                    item_notes.append(f"negative control operator fired: {negative_operator_id}")
                    failures.append(
                        {
                            "stage": "precondition",
                            "item_id": item_id,
                            "error": f"negative control operator fired: {negative_operator_id}",
                        }
                    )
        elif expected_positive_ids:
            positive_expected += len(expected_positive_ids)
            applicable_ids, error = _applicable_operator_ids(record)
            if error:
                item_notes.append(f"positive precondition audit unavailable: {error}")
            for operator_id in expected_positive_ids:
                if operator_id in applicable_ids:
                    positive_hits += 1
                else:
                    item_notes.append(f"expected operator not applicable: {operator_id}")
                    failures.append(
                        {
                            "stage": "precondition",
                            "item_id": item_id,
                            "operator_id": operator_id,
                            "error": "expected operator not applicable",
                        }
                    )

        certificates = extract_certificates(record)
        all_certificates.extend(certificates)
        certificate_validations: list[dict[str, Any]] = []
        for certificate in certificates:
            validation = validate_certificate(record, certificate)
            validation.update(compute_mev_lite(validation))
            mev_v1 = compute_mev_v1(validation)
            validation.update(mev_v1)
            validation_status = str(validation.get("mev_status") or "failed")
            if validation_status == "deferred_composite":
                composite_deferred_count += 1
            if validation.get("single_operator_certificate"):
                single_operator_certificate_scores.append(float(validation["mev_lite"]))
                if validation_status == "validated":
                    validated_single_operator_certificates += 1
            failure_type = _certificate_failure_type(validation)
            deferred_reason = _certificate_deferred_reason(validation)
            certificate_validations.append(validation)
            all_certificate_scores.append(float(validation["mev_lite"]))
            certificate_rows.append(
                {
                    **validation,
                    "applied_operator_ids": validation.get("applied_operator_ids") or [],
                    "validation_status": validation_status,
                    "failure_type": failure_type,
                    "deferred_reason": deferred_reason,
                    "notes": "; ".join(validation.get("notes") or []),
                }
            )
            if validation.get("parse_failure"):
                warnings.append(
                    {
                        "stage": "certificate",
                        "warning_type": "answer_parse_fallback",
                        "item_id": item_id,
                        "certificate_id": validation.get("certificate_id"),
                        "notes": validation.get("notes") or [],
                    }
                )
            if validation_status == "deferred_composite":
                deferred.append(
                    {
                        "stage": "certificate",
                        "item_id": item_id,
                        "certificate_id": validation.get("certificate_id"),
                        "deferred_reason": deferred_reason,
                        "mev_lite": validation["mev_lite"],
                        "mev_v1": validation.get("mev_v1"),
                        "notes": validation.get("notes") or [],
                    }
                )
            elif validation_status == "failed":
                failures.append(
                    {
                        "stage": "certificate",
                        "item_id": item_id,
                        "certificate_id": validation.get("certificate_id"),
                        "failure_type": failure_type,
                        "mev_lite": validation["mev_lite"],
                        "mev_v1": validation.get("mev_v1"),
                        "notes": validation.get("notes") or [],
                    }
                )

        if record.get("distractor_set"):
            slate_metrics = compute_slate_mdv_lite(record, certificates, certificate_validations)
            slate_rows.append(
                {
                    "item_id": item_id,
                    "num_distractors": len(record.get("distractor_set") or []),
                    "allowed_operator_ids": record.get("allowed_operator_ids") or [],
                    "notes": "",
                    **slate_metrics,
                }
            )

        if not leakage_ok:
            failures.append({"stage": "leakage", "item_id": item_id, "notes": leakage_notes})
        if not schema_ok:
            failures.append({"stage": "schema", "item_id": item_id, "notes": schema_notes})

        item_rows.append(
            {
                "item_id": item_id,
                "item_role": record.get("item_role"),
                "domain": record.get("domain"),
                "raw_answer_type": record.get("_audit", {}).get("raw_answer_type"),
                "normalized_answer_type": record.get("answer_type"),
                "allowed_operator_ids": record.get("allowed_operator_ids") or [],
                "target_error_operator_id": record.get("target_error_operator_id"),
                "target_error_operator_ids": record.get("target_error_operator_ids") or [],
                "negative_control_for_operator_id": record.get("negative_control_for_operator_id"),
                "num_certificates": len(certificates),
                "leakage_pass": leakage_ok,
                "schema_compatible": schema_ok,
                "cei_readiness": cei_readiness(record),
                "notes": "; ".join(item_notes),
            }
        )

    certificate_signature_counts = Counter(_operator_signature(certificate) for certificate in all_certificates)
    summary = {
        "total_items": len(records),
        "items_by_role": dict(sorted(role_counts.items())),
        "items_by_domain": dict(sorted(domain_counts.items())),
        "answer_type_raw_counts": dict(sorted(raw_answer_type_counts.items())),
        "answer_type_normalized_counts": dict(sorted(normalized_answer_type_counts.items())),
        "total_certificates": len(all_certificates),
        "certificates_by_operator_signature": dict(sorted(certificate_signature_counts.items())),
        "single_operator_certificates": sum(
            1 for certificate in all_certificates if len(certificate.get("applied_operator_ids") or []) == 1
        ),
        "composite_certificates": sum(
            1 for certificate in all_certificates if len(certificate.get("applied_operator_ids") or []) > 1
        ),
        "leakage_pass_rate": leakage_passes / len(records) if records else 0.0,
        "certificate_mev_lite_mean": (
            sum(all_certificate_scores) / len(all_certificate_scores) if all_certificate_scores else 0.0
        ),
        "certificate_mev_lite_mean_interpretation": "counts deferred composite certificates as zero",
        "validated_scope": "single_operator_single_divergence",
        "validated_single_operator_certificates": validated_single_operator_certificates,
        "single_operator_mev_lite_mean": (
            sum(single_operator_certificate_scores) / len(single_operator_certificate_scores)
            if single_operator_certificate_scores
            else 0.0
        ),
        "mev_lite_all_counting_deferred_as_zero": (
            sum(all_certificate_scores) / len(all_certificate_scores) if all_certificate_scores else 0.0
        ),
        "composite_deferred_count": composite_deferred_count,
        "composite_deferred_rate": (
            composite_deferred_count / len(all_certificates) if all_certificates else 0.0
        ),
        "hard_failure_count": len(failures),
        "deferred_count": len(deferred),
        "precondition_positive_recall": positive_hits / positive_expected if positive_expected else 0.0,
        "negative_control_false_positive_rate": (
            negative_false_positives / negative_expected if negative_expected else 0.0
        ),
        "transfer_item_slate_count": sum(1 for record in records if record.get("item_role") == "transfer_item" and record.get("distractor_set")),
    }

    _write_json(output_dir / "dataset_summary.json", summary)
    _write_csv(output_dir / "item_audit.csv", ITEM_AUDIT_COLUMNS, item_rows)
    _write_csv(output_dir / "certificate_audit.csv", CERTIFICATE_AUDIT_COLUMNS, certificate_rows)
    _write_csv(output_dir / "slate_audit.csv", SLATE_AUDIT_COLUMNS, slate_rows)
    _write_jsonl(output_dir / "failures.jsonl", failures)
    _write_jsonl(output_dir / "deferred.jsonl", deferred)
    _write_jsonl(output_dir / "warnings.jsonl", warnings)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    summary = run_audit(args.input, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
