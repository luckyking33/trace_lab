"""Deterministic leakage guard for mechanism-only experiments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class LeakageError(RuntimeError):
    """Raised when a mechanism-only payload contains forbidden information."""


FORBIDDEN_KEYS: set[str] = {
    "human_response_dist",
    "distractors",
    "original_options",
    "original_distractors",
    "seed_candidates",
    "top_seed_candidates",
    "distractor_meta.seed_candidates",
    "item_stats.student_choice",
    "student_choice",
    "response_distribution",
    "choice_distribution",
}

CANARY_PATTERNS = [
    "CANARY_DO_NOT_USE",
    "ORIGINAL_DISTRACTOR_CANARY",
]


def _path_join(parent: str, key: str) -> str:
    return f"{parent}.{key}" if parent else key


def _matches_forbidden_path(path: str, key: str, forbidden_key: str) -> bool:
    if "." in forbidden_key:
        return path == forbidden_key or path.endswith(f".{forbidden_key}")
    return key == forbidden_key or path == forbidden_key


def scan_forbidden_keys(
    obj: Any, forbidden_keys: set[str] | None = None, *, _path: str = ""
) -> list[str]:
    """Recursively scan dict/list/string objects for forbidden key names or paths."""

    forbidden = forbidden_keys or FORBIDDEN_KEYS
    matches: list[str] = []

    if isinstance(obj, Mapping):
        for raw_key, value in obj.items():
            key = str(raw_key)
            path = _path_join(_path, key)
            for forbidden_key in sorted(forbidden):
                if _matches_forbidden_path(path, key, forbidden_key):
                    matches.append(path)
            matches.extend(scan_forbidden_keys(value, forbidden, _path=path))
        return matches

    if isinstance(obj, (list, tuple)):
        for idx, value in enumerate(obj):
            matches.extend(scan_forbidden_keys(value, forbidden, _path=f"{_path}[{idx}]"))
        return matches

    if isinstance(obj, str):
        location = _path or "<string>"
        for forbidden_key in sorted(forbidden):
            if forbidden_key in obj:
                matches.append(f"{location}:{forbidden_key}")
        return matches

    return matches


def scan_canary_patterns(obj: Any, *, _path: str = "") -> list[str]:
    """Recursively scan payload values for canary strings."""

    matches: list[str] = []
    if isinstance(obj, Mapping):
        for raw_key, value in obj.items():
            key = str(raw_key)
            path = _path_join(_path, key)
            if any(pattern in key for pattern in CANARY_PATTERNS):
                matches.append(path)
            matches.extend(scan_canary_patterns(value, _path=path))
        return matches

    if isinstance(obj, (list, tuple)):
        for idx, value in enumerate(obj):
            matches.extend(scan_canary_patterns(value, _path=f"{_path}[{idx}]"))
        return matches

    if isinstance(obj, str):
        location = _path or "<string>"
        for pattern in CANARY_PATTERNS:
            if pattern in obj:
                matches.append(f"{location}:{pattern}")
        return matches

    return matches


def assert_no_leakage_payload(
    payload: Mapping[str, Any], forbidden_keys: set[str] | None = None
) -> None:
    """Raise LeakageError if forbidden keys or canary strings are found."""

    forbidden_matches = scan_forbidden_keys(payload, forbidden_keys)
    canary_matches = scan_canary_patterns(payload)
    if forbidden_matches or canary_matches:
        parts = []
        if forbidden_matches:
            parts.append(f"forbidden={sorted(set(forbidden_matches))}")
        if canary_matches:
            parts.append(f"canary={sorted(set(canary_matches))}")
        raise LeakageError("Leakage detected: " + "; ".join(parts))


def build_leakage_audit(payload: Mapping[str, Any]) -> dict[str, bool | list[str]]:
    """Return audit metadata with used_* flags and scan pass flags."""

    forbidden_matches = sorted(set(scan_forbidden_keys(payload)))
    canary_matches = sorted(set(scan_canary_patterns(payload)))
    joined = "\n".join(forbidden_matches)
    return {
        "used_human_response_dist": "human_response_dist" in joined
        or "response_distribution" in joined
        or "choice_distribution" in joined,
        "used_seed_candidates": "seed_candidates" in joined,
        "used_original_distractors": "original_distractors" in joined
        or "original_options" in joined
        or "distractors" in joined,
        "forbidden_key_scan_passed": not forbidden_matches,
        "canary_scan_passed": not canary_matches,
        "forbidden_matches": forbidden_matches,
        "canary_matches": canary_matches,
    }
