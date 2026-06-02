"""Candidate-level Baseline Evaluator v0 scoring."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from respondent_lab.certificates.validation import answer_equivalent
from respondent_lab.io.normalization import normalize_answer_object, normalize_item_record
from respondent_lab.evaluation.slate_metrics import compute_slate_metrics


FINAL_KNOWN_CERTIFIED = "known_certified"
FINAL_SELF_CERTIFIED = "self_certified"
FINAL_REVIEW = "incorrect_unmatched_review"
FINAL_EQUIVALENT_TO_CORRECT = "invalid_equivalent_to_correct"
FINAL_PARSE_FAILURE = "invalid_parse_failure"
FINAL_DUPLICATE = "invalid_duplicate"


def evaluate_generated_candidate(
    item_record: Any,
    generated_candidate: Any,
    certificate_bank_for_item: list[Any],
    correct_answer: Any,
) -> dict[str, Any]:
    """Evaluate one generated candidate against gold correctness and known certificates."""

    item = _normalize_item(item_record)
    item_id = str(_get(item, "item_id", "") or "")
    item_answer_type = _item_answer_type(item, correct_answer)
    normalized_candidate = _normalize_candidate(generated_candidate, item_answer_type)
    notes = list(normalized_candidate.get("notes") or [])

    candidate_id = str(
        _get(generated_candidate, "candidate_id")
        or _get(generated_candidate, "id")
        or normalized_candidate.get("candidate_id")
        or ""
    )
    raw_answer = normalized_candidate.get("raw_answer")
    normalized_answer = normalized_candidate.get("normalized_answer")
    parse_success = bool(normalized_candidate.get("parse_success"))

    normalized_correct = _coerce_answer_object(correct_answer, item_answer_type)
    incorrectness: bool | None = None
    if parse_success and normalized_answer and normalized_correct:
        equivalent_to_correct, parse_fallback = _answers_equivalent(normalized_answer, normalized_correct)
        if parse_fallback:
            _add_note(notes, "parse_fallback=true")
        incorrectness = not equivalent_to_correct
    elif parse_success:
        _add_note(notes, "missing_correct_answer")

    same_item_bank = _filter_bank_for_item(certificate_bank_for_item, item_id)
    match = _match_known_certificate(normalized_answer, same_item_bank, item_answer_type, notes) if (
        parse_success and incorrectness is True
    ) else None

    operator_id = _get(generated_candidate, "operator_id") or _get(generated_candidate, "operator_ids")
    wrong_solution_trace = _get(generated_candidate, "wrong_solution_trace")
    self_certificate_present = bool(operator_id) and _value_present(wrong_solution_trace)
    self_mev_v1 = None
    if self_certificate_present:
        _add_note(notes, "self_validation_not_implemented")

    result = {
        "item_id": item_id,
        "candidate_id": candidate_id,
        "raw_answer": raw_answer,
        "normalized_answer": normalized_answer,
        "parse_success": parse_success,
        "incorrectness": incorrectness,
        "duplicate_within_slate": False,
        "duplicate_of_candidate_id": None,
        "known_certificate_match": match is not None,
        "matched_certificate_id": _get(match, "certificate_id") if match else None,
        "matched_operator_ids": _get(match, "operator_ids") if match else [],
        "matched_operator_signature": _get(match, "operator_signature") if match else None,
        "matched_mev_v1": _get(match, "mev_v1") if match else None,
        "matched_cei_score": _get(match, "cei_score") if match else None,
        "matched_mdv_v1": _get(match, "mdv_v1") if match else None,
        "matched_cei_status": _get(match, "cei_status") if match else None,
        "self_certificate_present": self_certificate_present,
        "self_mev_v1": self_mev_v1,
        "final_certification_status": "",
        "notes": notes,
    }
    result["final_certification_status"] = _final_status(result)
    return result


def evaluate_generated_item(
    item_record: Any,
    generated_output: Any,
    certificate_bank_for_item: list[Any],
) -> dict[str, Any]:
    """Evaluate a generated slate for one item and return candidate and slate metrics."""

    item = _normalize_item(item_record)
    item_id = str(_get(item, "item_id", "") or "")
    correct_answer = _get(item, "correct_answer")
    bank_for_item = _filter_bank_for_item(certificate_bank_for_item, item_id)

    candidate_records: list[dict[str, Any]] = []
    candidates = _candidate_sequence(generated_output)
    for idx, candidate in enumerate(candidates, start=1):
        candidate_obj = candidate
        if _get(candidate_obj, "candidate_id") in (None, ""):
            candidate_obj = _with_default_candidate_id(candidate_obj, f"candidate_{idx}")
        record = evaluate_generated_candidate(item, candidate_obj, bank_for_item, correct_answer)
        candidate_records.append(record)

    _mark_duplicates(candidate_records)
    slate = compute_slate_metrics(candidate_records, bank_for_item)
    return {
        "item_id": item_id,
        "candidate_evaluations": candidate_records,
        "slate_metrics": slate,
    }


def _normalize_item(item_record: Any) -> dict[str, Any]:
    item = _plain(item_record)
    if not isinstance(item, dict):
        return {}
    try:
        return normalize_item_record(item)
    except Exception:
        return item


def _normalize_candidate(candidate: Any, item_answer_type: str | None) -> dict[str, Any]:
    worker_result = _worker1_normalize_candidate(candidate, item_answer_type)
    if worker_result is not None:
        parsed = _plain(worker_result)
        if isinstance(parsed, dict) and "normalized_answer" in parsed:
            normalized_answer = _coerce_answer_object(parsed.get("normalized_answer"), item_answer_type)
            return {
                "candidate_id": parsed.get("candidate_id"),
                "raw_answer": parsed.get("raw_answer", _get(candidate, "answer")),
                "normalized_answer": normalized_answer,
                "parse_success": bool(parsed.get("parse_success", normalized_answer is not None)),
                "notes": _coerce_notes(parsed.get("notes") or parsed.get("parse_notes")),
            }

    raw_answer = _get(candidate, "answer", None)
    if raw_answer is None and not isinstance(candidate, dict) and not _has_attr(candidate, "answer"):
        raw_answer = candidate
    if raw_answer is None:
        raw_answer = _get(candidate, "raw_answer", None)

    notes: list[str] = []
    normalized_answer = _coerce_answer_object(raw_answer, item_answer_type)
    parse_success = normalized_answer is not None and _value_present(normalized_answer.get("value"))
    if not parse_success:
        if raw_answer is None:
            _add_note(notes, "missing_answer")
        elif isinstance(raw_answer, dict) and not {"type", "value"} <= set(raw_answer):
            _add_note(notes, "unsupported_answer_object")
        elif item_answer_type is None and not isinstance(raw_answer, dict):
            _add_note(notes, "missing_item_answer_type")
        else:
            _add_note(notes, "answer_parse_failure")

    return {
        "candidate_id": _get(candidate, "candidate_id") or _get(candidate, "id"),
        "raw_answer": _plain(raw_answer),
        "normalized_answer": normalized_answer,
        "parse_success": parse_success,
        "notes": notes,
    }


def _worker1_normalize_candidate(candidate: Any, item_answer_type: str | None) -> Any | None:
    try:
        from respondent_lab.evaluation.generated_outputs import (  # type: ignore[import-not-found]
            normalize_generated_candidate,
        )
    except Exception:
        return None
    try:
        return normalize_generated_candidate(candidate, item_answer_type=item_answer_type)
    except Exception:
        return None


def _coerce_answer_object(raw_answer: Any, item_answer_type: str | None) -> dict[str, Any] | None:
    raw_answer = _plain(raw_answer)
    if isinstance(raw_answer, str):
        parsed = _json_loads_or_none(raw_answer)
        if isinstance(parsed, dict) and {"type", "value"} <= set(parsed):
            raw_answer = parsed
    if isinstance(raw_answer, dict) and {"type", "value"} <= set(raw_answer):
        try:
            return normalize_answer_object(raw_answer)
        except Exception:
            return None
    if raw_answer is None or item_answer_type is None:
        return None
    try:
        return normalize_answer_object({"type": item_answer_type, "value": raw_answer})
    except Exception:
        return None


def _answers_equivalent(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, bool]:
    try:
        return answer_equivalent(left, right)
    except Exception:
        return _answer_string_key(left) == _answer_string_key(right), True


def _match_known_certificate(
    normalized_answer: dict[str, Any] | None,
    certificate_bank_for_item: list[Any],
    item_answer_type: str | None,
    notes: list[str],
) -> dict[str, Any] | None:
    if normalized_answer is None:
        return None

    matches: list[dict[str, Any]] = []
    for raw_record in sorted(certificate_bank_for_item, key=lambda row: str(_get(row, "certificate_id", ""))):
        bank_record = _normalize_bank_record(raw_record, item_answer_type)
        bank_answer = bank_record.get("candidate_answer")
        if not bank_answer:
            continue
        equivalent, parse_fallback = _answers_equivalent(normalized_answer, bank_answer)
        if parse_fallback:
            _add_note(notes, "parse_fallback=true")
        if equivalent:
            matches.append(bank_record)

    if not matches:
        return None
    if len(matches) > 1:
        _add_note(notes, f"multiple_known_certificate_matches={len(matches)}")
    return matches[0]


def _normalize_bank_record(raw_record: Any, item_answer_type: str | None) -> dict[str, Any]:
    record = _plain(raw_record)
    if not isinstance(record, dict):
        return {}
    candidate_answer = _coerce_answer_object(record.get("candidate_answer"), item_answer_type)
    operator_ids = _operator_ids_from_record(record)
    return {
        **record,
        "candidate_answer": candidate_answer,
        "operator_ids": operator_ids,
        "operator_signature": _operator_signature(record.get("operator_signature"), operator_ids),
        "mev_v1": _float_or_none(record.get("mev_v1")),
        "cei_score": _float_or_none(record.get("cei_score")),
        "mdv_v1": _float_or_none(record.get("mdv_v1")),
        "cei_status": record.get("cei_status"),
    }


def _filter_bank_for_item(certificate_bank: list[Any], item_id: str) -> list[Any]:
    records = list(certificate_bank or [])
    if not item_id:
        return records
    explicit_item_records = [record for record in records if _get(record, "item_id") not in (None, "")]
    if explicit_item_records:
        return [
            record
            for record in explicit_item_records
            if str(_get(record, "item_id") or "") == item_id
        ]
    return records


def _mark_duplicates(candidate_records: list[dict[str, Any]]) -> None:
    previous: list[dict[str, Any]] = []
    for record in candidate_records:
        if not record.get("parse_success") or not record.get("normalized_answer"):
            record["final_certification_status"] = _final_status(record)
            continue
        duplicate_of = None
        for prior in previous:
            equivalent, parse_fallback = _answers_equivalent(
                record["normalized_answer"], prior["normalized_answer"]
            )
            if parse_fallback:
                _add_note(record.setdefault("notes", []), "parse_fallback=true")
            if equivalent:
                duplicate_of = prior.get("candidate_id") or ""
                break
        if duplicate_of is not None:
            record["duplicate_within_slate"] = True
            record["duplicate_of_candidate_id"] = duplicate_of
        else:
            previous.append(record)
        record["final_certification_status"] = _final_status(record)


def _final_status(record: dict[str, Any]) -> str:
    if not record.get("parse_success"):
        return FINAL_PARSE_FAILURE
    if record.get("duplicate_within_slate"):
        return FINAL_DUPLICATE
    if record.get("incorrectness") is False:
        return FINAL_EQUIVALENT_TO_CORRECT
    if record.get("known_certificate_match"):
        return FINAL_KNOWN_CERTIFIED
    if _float_or_none(record.get("self_mev_v1")) == 1.0:
        return FINAL_SELF_CERTIFIED
    if record.get("incorrectness") is True:
        return FINAL_REVIEW
    return FINAL_PARSE_FAILURE


def _candidate_sequence(generated_output: Any) -> list[Any]:
    if isinstance(generated_output, list):
        return list(generated_output)
    for key in ("candidates", "generated_candidates", "outputs"):
        candidates = _get(generated_output, key)
        if candidates is not None:
            return list(candidates or [])
    answer = _get(generated_output, "answer")
    if answer is not None:
        candidate = {
            "candidate_id": _get(generated_output, "candidate_id") or "candidate_1",
            "answer": answer,
            "explanation": _get(generated_output, "explanation"),
            "error_label": _get(generated_output, "error_label"),
            "operator_id": _get(generated_output, "operator_id"),
            "wrong_solution_trace": _get(generated_output, "wrong_solution_trace"),
            "metadata": _get(generated_output, "metadata"),
        }
        return [candidate]
    return []


def _with_default_candidate_id(candidate: Any, candidate_id: str) -> Any:
    if isinstance(candidate, dict):
        updated = dict(candidate)
        updated["candidate_id"] = candidate_id
        return updated
    return {"candidate_id": candidate_id, "answer": _get(candidate, "answer", candidate)}


def _item_answer_type(item_record: dict[str, Any], correct_answer: Any) -> str | None:
    answer_type = _get(item_record, "answer_type")
    if answer_type:
        return str(answer_type)
    correct = _plain(correct_answer) or _get(item_record, "correct_answer")
    if isinstance(correct, dict) and correct.get("type"):
        return str(correct["type"])
    return None


def _operator_ids_from_record(record: dict[str, Any]) -> list[str]:
    for key in ("operator_ids", "applied_operator_ids", "matched_operator_ids"):
        ids = _parse_sequence(record.get(key))
        if ids:
            return [str(operator_id) for operator_id in ids if operator_id]
    signature = _parse_sequence(record.get("operator_signature"))
    return [str(operator_id) for operator_id in signature if operator_id]


def _operator_signature(raw_signature: Any, operator_ids: list[str]) -> tuple[str, ...]:
    parsed = _parse_sequence(raw_signature)
    if parsed:
        return tuple(str(operator_id) for operator_id in parsed if operator_id)
    return tuple(operator_ids)


def _parse_sequence(value: Any) -> list[Any]:
    value = _plain(value)
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str):
        parsed = _json_loads_or_none(value)
        if isinstance(parsed, list):
            return parsed
        stripped = value.strip()
        for separator in ("+", "|", ","):
            if separator in stripped:
                return [part.strip() for part in stripped.split(separator) if part.strip()]
        return [stripped] if stripped else []
    return [value]


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


def _get(obj: Any, key: str, default: Any = None) -> Any:
    obj = _plain(obj)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _has_attr(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


def _json_loads_or_none(value: str) -> Any | None:
    try:
        return json.loads(value)
    except Exception:
        return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, "", "None", "none", "null"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _value_present(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _answer_string_key(answer: dict[str, Any]) -> str:
    return json.dumps(_plain(answer.get("value")), ensure_ascii=False, sort_keys=True)


def _coerce_notes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


def _add_note(notes: list[str], note: str) -> None:
    if note not in notes:
        notes.append(note)
