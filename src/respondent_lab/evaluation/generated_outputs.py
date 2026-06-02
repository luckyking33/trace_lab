"""Generated-output schema helpers for Baseline Evaluator v0."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from respondent_lab.io.normalization import normalize_answer_object, normalize_answer_type


@dataclass
class GeneratedCandidate:
    """One generated candidate answer for an item."""

    candidate_id: str
    answer: dict[str, Any] | str
    explanation: str | None = None
    error_label: str | None = None
    operator_id: str | None = None
    wrong_solution_trace: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.wrong_solution_trace is None:
            self.wrong_solution_trace = []
        else:
            self.wrong_solution_trace = [
                copy.deepcopy(step) for step in self.wrong_solution_trace if isinstance(step, dict)
            ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "answer": copy.deepcopy(self.answer),
            "explanation": self.explanation,
            "error_label": self.error_label,
            "operator_id": self.operator_id,
            "wrong_solution_trace": copy.deepcopy(self.wrong_solution_trace),
            "metadata": copy.deepcopy(self.metadata),
        }


@dataclass
class GeneratedItemOutput:
    """Generated candidates for one item."""

    run_id: str = ""
    method: str = ""
    prompt_version: str | None = None
    model: str | None = None
    item_id: str = ""
    visible_input_hash: str | None = None
    candidates: list[GeneratedCandidate] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "method": self.method,
            "prompt_version": self.prompt_version,
            "model": self.model,
            "item_id": self.item_id,
            "visible_input_hash": self.visible_input_hash,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "metadata": copy.deepcopy(self.metadata),
        }


def load_generated_outputs(path: str | Path) -> list[GeneratedItemOutput]:
    """Load generated item outputs from JSONL."""

    output_path = Path(path)
    if not output_path.exists():
        raise FileNotFoundError(output_path)

    outputs: list[GeneratedItemOutput] = []
    with output_path.open("r", encoding="utf-8") as handle:
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
            outputs.append(_item_output_from_payload(payload, line_number=line_number))
    return outputs


def normalize_generated_candidate(
    candidate: GeneratedCandidate | dict[str, Any] | str,
    item_answer_type: str | None = None,
) -> dict[str, Any]:
    """Normalize a generated candidate answer into evaluator-ready fields."""

    candidate_obj = _coerce_candidate(candidate)
    notes: list[str] = []
    try:
        normalized_answer, normalization_notes = _coerce_answer_object(
            candidate_obj.answer,
            item_answer_type=item_answer_type,
        )
        notes.extend(normalization_notes)
        parse_success = True
        parse_error = None
    except Exception as exc:  # noqa: BLE001 - parse errors are reported structurally.
        normalized_answer = None
        parse_success = False
        parse_error = str(exc)

    return {
        "candidate_id": candidate_obj.candidate_id,
        "raw_answer": copy.deepcopy(candidate_obj.answer),
        "normalized_answer": normalized_answer,
        "parse_success": parse_success,
        "parse_error": parse_error,
        "explanation": candidate_obj.explanation,
        "error_label": candidate_obj.error_label,
        "operator_id": candidate_obj.operator_id,
        "wrong_solution_trace": copy.deepcopy(candidate_obj.wrong_solution_trace),
        "self_certificate_present": bool(candidate_obj.operator_id and candidate_obj.wrong_solution_trace),
        "metadata": copy.deepcopy(candidate_obj.metadata),
        "notes": notes,
    }


def _item_output_from_payload(payload: dict[str, Any], *, line_number: int) -> GeneratedItemOutput:
    item_id = str(payload.get("item_id") or "")
    if not item_id:
        raise ValueError(f"Generated output on line {line_number} is missing item_id")

    raw_candidates = payload.get("candidates")
    if raw_candidates is None and any(key in payload for key in ("answer", "answer_object", "raw_answer")):
        raw_candidates = [payload]
    if not isinstance(raw_candidates, list):
        raise ValueError(f"Generated output on line {line_number} must contain a candidates list")

    candidates = [
        _candidate_from_payload(candidate_payload, index=index)
        for index, candidate_payload in enumerate(raw_candidates, start=1)
    ]
    known_keys = {
        "item_id",
        "method",
        "run_id",
        "prompt_version",
        "model",
        "visible_input_hash",
        "candidates",
        "answer",
        "answer_object",
        "raw_answer",
    }
    metadata = dict(payload.get("metadata") or {})
    extra = {key: copy.deepcopy(value) for key, value in payload.items() if key not in known_keys and key != "metadata"}
    if extra:
        metadata.setdefault("extra", extra)

    return GeneratedItemOutput(
        run_id=_required_summary_str(payload.get("run_id")),
        method=_required_summary_str(payload.get("method")),
        prompt_version=_optional_str(payload.get("prompt_version")),
        model=_optional_str(payload.get("model")),
        item_id=item_id,
        visible_input_hash=_optional_str(payload.get("visible_input_hash")),
        candidates=candidates,
        metadata=metadata,
    )


def _candidate_from_payload(payload: Any, *, index: int) -> GeneratedCandidate:
    if isinstance(payload, GeneratedCandidate):
        return payload
    if not isinstance(payload, dict):
        return GeneratedCandidate(candidate_id=f"candidate_{index}", answer=_schema_answer(payload))

    answer = _extract_answer(payload)
    candidate_id = str(payload.get("candidate_id") or payload.get("id") or f"candidate_{index}")
    trace = _extract_wrong_solution_trace(payload)
    known_keys = {
        "answer",
        "answer_object",
        "candidate_id",
        "error_label",
        "explanation",
        "id",
        "metadata",
        "normalized_answer",
        "operator_id",
        "operator_ids",
        "applied_operator_ids",
        "raw_answer",
        "wrong_solution_trace",
        "wrong_trace",
        "trace",
    }
    metadata = dict(payload.get("metadata") or {})
    extra = {key: copy.deepcopy(value) for key, value in payload.items() if key not in known_keys}
    if extra:
        metadata.setdefault("extra", extra)

    return GeneratedCandidate(
        candidate_id=candidate_id,
        answer=_schema_answer(answer),
        explanation=_optional_str(payload.get("explanation")),
        error_label=_optional_str(payload.get("error_label")),
        operator_id=_extract_operator_id(payload),
        wrong_solution_trace=trace,
        metadata=metadata,
    )


def _coerce_candidate(candidate: GeneratedCandidate | dict[str, Any] | str) -> GeneratedCandidate:
    if isinstance(candidate, GeneratedCandidate):
        return candidate
    return _candidate_from_payload(candidate, index=1)


def _extract_answer(payload: dict[str, Any]) -> Any:
    if "answer" in payload:
        return payload["answer"]
    if "answer_object" in payload:
        return payload["answer_object"]
    if "normalized_answer" in payload:
        return payload["normalized_answer"]
    if "raw_answer" in payload:
        return payload["raw_answer"]
    if "type" in payload and "value" in payload:
        return {"type": payload["type"], "value": payload["value"]}
    raise ValueError("candidate is missing answer")


def _extract_operator_id(payload: dict[str, Any]) -> str | None:
    operator_id = payload.get("operator_id")
    if operator_id:
        return str(operator_id)
    for key in ("operator_ids", "applied_operator_ids"):
        value = payload.get(key)
        if isinstance(value, list) and len(value) == 1 and value[0]:
            return str(value[0])
    return None


def _extract_wrong_solution_trace(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_trace = payload.get("wrong_solution_trace")
    if raw_trace is None:
        raw_trace = payload.get("wrong_trace")
    if raw_trace is None:
        raw_trace = payload.get("trace")
    if isinstance(raw_trace, dict) and isinstance(raw_trace.get("steps"), list):
        raw_trace = raw_trace["steps"]
    if not isinstance(raw_trace, list):
        return []
    return [copy.deepcopy(step) for step in raw_trace if isinstance(step, dict)]


def _coerce_answer_object(raw_answer: Any, *, item_answer_type: str | None) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    if isinstance(raw_answer, dict):
        if "type" in raw_answer and "value" in raw_answer:
            if not _value_present(raw_answer.get("value")):
                raise ValueError("candidate answer value is empty")
            return normalize_answer_object(raw_answer), notes
        if item_answer_type is not None and "value" in raw_answer:
            value = raw_answer["value"]
            if not _value_present(value):
                raise ValueError("candidate answer value is empty")
            return normalize_answer_object({"type": item_answer_type, "value": value}), notes
        raise ValueError("candidate answer dict must include type and value")

    if not _value_present(raw_answer):
        raise ValueError("candidate answer value is empty")

    answer_type = item_answer_type
    if answer_type is None:
        answer_type = "formula"
        notes.append("item_answer_type_missing_default_formula")
    normalized_type, _ = normalize_answer_type(answer_type)
    value = raw_answer
    if normalized_type == "answer_set" and not isinstance(value, list):
        value = [value]
    return normalize_answer_object({"type": normalized_type, "value": value}), notes


def _schema_answer(answer: Any) -> dict[str, Any] | str:
    if isinstance(answer, dict):
        return copy.deepcopy(answer)
    if isinstance(answer, str):
        return answer
    return str(answer)


def _value_present(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _required_summary_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
