from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class LeakageError(RuntimeError):
    pass


PROMPT_FORBIDDEN_KEYS: set[str] = {
    "choices",
    "options",
    "distractors",
    "human_response_dist",
    "student_choice",
    "choice_logs",
    "seed_candidates",
    "item_stats",
    "original_options",
    "option_frequency",
    "original_distractors",
    "top_seed_candidates",
    "distractor_meta.seed_candidates",
    "item_stats.student_choice",
    "response_distribution",
    "choice_distribution",
}

LEAKAGE_FIELD_HINTS = {
    "choices",
    "options",
    "distractors",
    "human_response_dist",
    "student_choice",
    "choice_logs",
    "seed_candidates",
    "item_stats",
    "original_options",
    "option_frequency",
    "original_distractors",
    "top_seed_candidates",
    "response_distribution",
    "choice_distribution",
}

CANARY_PATTERNS = ["CANARY_DO_NOT_USE", "ORIGINAL_DISTRACTOR_CANARY"]


def load_forbidden_keys(repo_root: Path) -> set[str]:
    config_path = repo_root / "configs" / "mechanism_only.yaml"
    keys = set(PROMPT_FORBIDDEN_KEYS)
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        keys.update(str(key) for key in loaded.get("forbidden_fields", []))
    return keys


def _path_join(parent: str, key: str) -> str:
    return f"{parent}.{key}" if parent else key


def _matches_forbidden_path(path: str, key: str, forbidden_key: str) -> bool:
    normalized_key = key.lower()
    normalized_path = path.lower()
    normalized_forbidden = forbidden_key.lower()
    if "." in normalized_forbidden:
        return normalized_path == normalized_forbidden or normalized_path.endswith(
            f".{normalized_forbidden}"
        )
    return normalized_key == normalized_forbidden or normalized_path == normalized_forbidden


def scan_forbidden_keys(
    obj: Any, forbidden_keys: set[str], *, _path: str = ""
) -> list[str]:
    matches: list[str] = []
    if isinstance(obj, Mapping):
        for raw_key, value in obj.items():
            key = str(raw_key)
            path = _path_join(_path, key)
            for forbidden_key in sorted(forbidden_keys):
                if _matches_forbidden_path(path, key, forbidden_key):
                    matches.append(path)
            matches.extend(scan_forbidden_keys(value, forbidden_keys, _path=path))
        return matches
    if isinstance(obj, list):
        for index, value in enumerate(obj):
            matches.extend(scan_forbidden_keys(value, forbidden_keys, _path=f"{_path}[{index}]"))
        return matches
    return matches


def scan_canary_patterns(obj: Any, *, _path: str = "") -> list[str]:
    matches: list[str] = []
    if isinstance(obj, Mapping):
        for raw_key, value in obj.items():
            key = str(raw_key)
            path = _path_join(_path, key)
            if any(pattern in key for pattern in CANARY_PATTERNS):
                matches.append(path)
            matches.extend(scan_canary_patterns(value, _path=path))
        return matches
    if isinstance(obj, list):
        for index, value in enumerate(obj):
            matches.extend(scan_canary_patterns(value, _path=f"{_path}[{index}]"))
        return matches
    if isinstance(obj, str):
        location = _path or "<string>"
        for pattern in CANARY_PATTERNS:
            if pattern in obj:
                matches.append(f"{location}:{pattern}")
        return matches
    return matches


def assert_no_leakage_payload(payload: Mapping[str, Any], forbidden_keys: set[str]) -> None:
    forbidden_matches = sorted(set(scan_forbidden_keys(payload, forbidden_keys)))
    canary_matches = sorted(set(scan_canary_patterns(payload)))
    if forbidden_matches or canary_matches:
        parts: list[str] = []
        if forbidden_matches:
            parts.append(f"forbidden={forbidden_matches}")
        if canary_matches:
            parts.append(f"canary={canary_matches}")
        raise LeakageError("Leakage detected: " + "; ".join(parts))


def record_leakage_warnings(record: Mapping[str, Any], forbidden_keys: set[str]) -> list[str]:
    return sorted(set(scan_forbidden_keys(record, forbidden_keys)))


def is_leakage_sensitive_field(field_name: str) -> bool:
    key = field_name.lower()
    return any(hint in key for hint in LEAKAGE_FIELD_HINTS)
