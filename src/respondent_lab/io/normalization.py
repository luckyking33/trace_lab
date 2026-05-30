"""Normalization helpers for manually curated math audit records."""

from __future__ import annotations

import copy
import json
import re
from typing import Any


ANSWER_TYPE_MAP: dict[str, str] = {
    "numeric": "numeric",
    "symbolic": "formula",
    "finite_set": "answer_set",
    "set_numeric": "answer_set",
    "set_symbolic": "answer_set",
    "set_condition": "answer_set",
    "formula": "formula",
    "answer_set": "answer_set",
}


def normalize_answer_type(raw_type: str) -> tuple[str, dict[str, Any]]:
    """Map source answer types onto verifier-supported answer types."""

    original = "" if raw_type is None else str(raw_type).strip()
    return ANSWER_TYPE_MAP.get(original, original), {"original_answer_type": original}


def _extract_braced(text: str, start: int) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    chars: list[str] = []
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            if depth:
                chars.append(char)
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return "".join(chars), idx + 1
            chars.append(char)
            continue
        chars.append(char)
    return None


def _replace_frac(text: str) -> str:
    result: list[str] = []
    idx = 0
    command = r"\frac"
    while idx < len(text):
        if not text.startswith(command, idx):
            result.append(text[idx])
            idx += 1
            continue

        cursor = idx + len(command)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        numerator = _extract_braced(text, cursor)
        if numerator is None:
            result.append(command)
            idx = cursor
            continue
        denominator = _extract_braced(text, numerator[1])
        if denominator is None:
            result.append(command)
            idx = cursor
            continue
        result.append(f"({numerator[0]})/({denominator[0]})")
        idx = denominator[1]
    return "".join(result)


def _replace_sqrt(text: str) -> str:
    result: list[str] = []
    idx = 0
    command = r"\sqrt"
    while idx < len(text):
        if not text.startswith(command, idx):
            result.append(text[idx])
            idx += 1
            continue

        cursor = idx + len(command)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        radicand = _extract_braced(text, cursor)
        if radicand is None:
            result.append(command)
            idx = cursor
            continue
        result.append(f"sqrt({radicand[0]})")
        idx = radicand[1]
    return "".join(result)


def _insert_common_multiplication(text: str) -> str:
    text = re.sub(r"(?<=\d)(?=[A-Za-z])", "*", text)
    text = re.sub(r"(?<=\d)(?=\()", "*", text)
    text = re.sub(r"(?<=\))(?=\()", "*", text)
    return text


def strip_latex_wrappers(text: str) -> str:
    """Strip simple LaTeX wrappers and convert common constructs for SymPy."""

    if not isinstance(text, str):
        return text

    normalized = text.strip()
    normalized = normalized.replace(r"\(", "").replace(r"\)", "")
    normalized = normalized.replace(r"\[", "").replace(r"\]", "")
    normalized = normalized.strip("$")
    normalized = normalized.replace(r"\left", "").replace(r"\right", "")
    normalized = normalized.replace(r"\cdot", "*").replace(r"\times", "*")
    normalized = normalized.replace(r"\quad", " ")
    normalized = normalized.replace(r"\pm", "+-").replace("±", "+-")
    normalized = normalized.replace("−", "-")
    normalized = normalized.replace("{", "{").replace("}", "}")

    previous = None
    while previous != normalized:
        previous = normalized
        normalized = _replace_frac(normalized)
        normalized = _replace_sqrt(normalized)

    normalized = normalized.replace("^", "**")
    normalized = _insert_common_multiplication(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _normalize_string_value(value: str) -> str:
    return strip_latex_wrappers(value)


def _normalize_math_value(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_string_value(value)
    if isinstance(value, list):
        return [_normalize_math_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_math_value(item) for item in value]
    if isinstance(value, dict):
        if "type" in value and "value" in value:
            return normalize_answer_object(value)
        return {key: _normalize_math_value(val) for key, val in value.items()}
    return value


def normalize_answer_object(answer: dict[str, Any]) -> dict[str, Any]:
    """Normalize an answer object's type and value while preserving raw value metadata."""

    normalized = copy.deepcopy(answer)
    raw_type = normalized.get("type", "")
    mapped_type, type_metadata = normalize_answer_type(raw_type)
    raw_value = copy.deepcopy(normalized.get("value"))
    normalized["type"] = mapped_type
    normalized["value"] = _normalize_math_value(raw_value)

    metadata = dict(normalized.get("metadata") or {})
    metadata.update(type_metadata)
    metadata["raw_value"] = raw_value
    metadata["latex_normalized"] = normalized["value"] != raw_value
    normalized["metadata"] = metadata
    return normalized


def normalize_trace_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize trace strings and mark divergence steps from metadata operator fields."""

    normalized_steps: list[dict[str, Any]] = []
    for raw_step in steps or []:
        step = copy.deepcopy(raw_step)
        metadata = dict(step.get("metadata") or {})
        for key in ("expr", "result"):
            if key in step:
                value = _normalize_math_value(step[key])
                if key == "result" and isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                step[key] = value
        for key in ("derived_answer", "answer"):
            if key in metadata:
                metadata[key] = _normalize_math_value(metadata[key])

        metadata_operator_id = metadata.get("error_operator_id") or metadata.get("operator_id")
        if metadata_operator_id:
            step.setdefault("operator_id", metadata_operator_id)
            if not step.get("operator_id"):
                step["operator_id"] = metadata_operator_id
            step["is_divergence"] = True
        step["metadata"] = metadata
        normalized_steps.append(step)
    return normalized_steps


def _normalize_record_sequence(values: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [_normalize_math_value(value) for value in values or []]


def normalize_item_record(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize all audit-relevant answer and trace fields on a raw JSONL record."""

    normalized = copy.deepcopy(record)
    raw_answer_type = str(normalized.get("answer_type") or normalized.get("correct_answer", {}).get("type", ""))
    mapped_answer_type, type_metadata = normalize_answer_type(raw_answer_type)
    normalized["answer_type"] = mapped_answer_type

    audit_metadata = dict(normalized.get("_audit") or {})
    audit_metadata.update(type_metadata)
    audit_metadata["raw_answer_type"] = raw_answer_type
    audit_metadata["normalized_answer_type"] = mapped_answer_type
    normalized["_audit"] = audit_metadata

    if isinstance(normalized.get("correct_answer"), dict):
        normalized["correct_answer"] = normalize_answer_object(normalized["correct_answer"])
    if isinstance(normalized.get("distractor_answer"), dict):
        normalized["distractor_answer"] = normalize_answer_object(normalized["distractor_answer"])

    if isinstance(normalized.get("solution_trace"), list):
        normalized["solution_trace"] = normalize_trace_steps(normalized["solution_trace"])
    if isinstance(normalized.get("wrong_solution_trace"), list):
        normalized["wrong_solution_trace"] = normalize_trace_steps(normalized["wrong_solution_trace"])

    normalized["givens"] = _normalize_record_sequence(normalized.get("givens"))
    normalized["constraints"] = _normalize_record_sequence(normalized.get("constraints"))

    distractor_set = []
    for distractor in normalized.get("distractor_set") or []:
        item = copy.deepcopy(distractor)
        if isinstance(item.get("answer"), dict):
            item["answer"] = normalize_answer_object(item["answer"])
        if isinstance(item.get("wrong_solution_trace"), list):
            item["wrong_solution_trace"] = normalize_trace_steps(item["wrong_solution_trace"])
        distractor_set.append(item)
    if "distractor_set" in normalized:
        normalized["distractor_set"] = distractor_set

    return normalized
