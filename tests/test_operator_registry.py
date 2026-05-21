from __future__ import annotations

import pytest

from respondent_lab.mechanisms.math_operators import ALG_SIGN_MOVE
from respondent_lab.mechanisms.operator_registry import (
    clear_registry,
    get_applicable_operators,
    get_operator,
    register_operator,
)
from respondent_lab.schemas.items import Item


def test_register_get_and_duplicate(payload_factory) -> None:
    clear_registry()
    register_operator(ALG_SIGN_MOVE)
    assert get_operator("ALG_SIGN_MOVE") is ALG_SIGN_MOVE
    with pytest.raises(ValueError):
        register_operator(ALG_SIGN_MOVE)

    item = Item.model_validate(payload_factory())
    assert [op.operator_id for op in get_applicable_operators(item)] == ["ALG_SIGN_MOVE"]


def test_get_unknown_operator_raises() -> None:
    clear_registry()
    with pytest.raises(KeyError):
        get_operator("UNKNOWN")
