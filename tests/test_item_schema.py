from __future__ import annotations

import pytest
from pydantic import ValidationError

from respondent_lab.audit.leakage_guard import LeakageError
from respondent_lab.schemas.items import Item


def test_valid_item_normalizes_trace(payload_factory) -> None:
    item = Item.model_validate(payload_factory())
    assert item.solution_trace.item_id == item.item_id
    assert len(item.solution_trace.steps) == 2


def test_missing_correct_answer_fails(payload_factory) -> None:
    payload = payload_factory()
    payload.pop("correct_answer")
    with pytest.raises(ValidationError):
        Item.model_validate(payload)


def test_missing_trace_fails(payload_factory) -> None:
    payload = payload_factory()
    payload.pop("solution_trace")
    with pytest.raises(ValidationError):
        Item.model_validate(payload)


def test_short_trace_fails(payload_factory) -> None:
    payload = payload_factory()
    payload["solution_trace"] = [payload["solution_trace"][0]]
    with pytest.raises(ValidationError):
        Item.model_validate(payload)


def test_forbidden_key_fails(payload_factory) -> None:
    payload = payload_factory()
    payload["seed_candidates"] = ["unsafe"]
    with pytest.raises((LeakageError, ValidationError)):
        Item.model_validate(payload)


def test_required_leakage_flags_must_be_true(payload_factory) -> None:
    payload = payload_factory()
    payload["leakage_flags"]["seed_candidates_removed"] = False
    with pytest.raises(ValidationError):
        Item.model_validate(payload)
