from __future__ import annotations

import pytest

from respondent_lab.audit.leakage_guard import (
    LeakageError,
    assert_no_leakage_payload,
    build_leakage_audit,
    scan_forbidden_keys,
)


def test_forbidden_key_scan_flat() -> None:
    assert scan_forbidden_keys({"distractors": []}) == ["distractors"]


def test_forbidden_key_scan_nested_dotted_path() -> None:
    matches = scan_forbidden_keys({"distractor_meta": {"seed_candidates": ["x"]}})
    assert "distractor_meta.seed_candidates" in matches


def test_forbidden_key_scan_list() -> None:
    matches = scan_forbidden_keys({"items": [{"seed_candidates": ["x"]}]})
    assert "items[0].seed_candidates" in matches


def test_forbidden_key_scan_string_prompt_text() -> None:
    matches = scan_forbidden_keys({"prompt": "Never include original_distractors here."})
    assert "prompt:original_distractors" in matches


def test_canary_raises_leakage_error() -> None:
    with pytest.raises(LeakageError):
        assert_no_leakage_payload({"prompt": "CANARY_DO_NOT_USE_9f3a"})


def test_build_leakage_audit_flags() -> None:
    audit = build_leakage_audit({"seed_candidates": ["x"]})
    assert audit["used_seed_candidates"] is True
    assert audit["forbidden_key_scan_passed"] is False
    assert audit["canary_scan_passed"] is True
