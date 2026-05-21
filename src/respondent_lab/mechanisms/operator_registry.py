"""Global deterministic registry for MVP error operators."""

from __future__ import annotations

from respondent_lab.mechanisms.base import ErrorOperator
from respondent_lab.schemas.items import Item

_REGISTRY: dict[str, ErrorOperator] = {}


def clear_registry() -> None:
    """Clear registry; intended for tests only."""

    _REGISTRY.clear()


def register_operator(op: ErrorOperator) -> None:
    if op.operator_id in _REGISTRY:
        raise ValueError(f"Operator already registered: {op.operator_id}")
    _REGISTRY[op.operator_id] = op


def get_operator(operator_id: str) -> ErrorOperator:
    try:
        return _REGISTRY[operator_id]
    except KeyError as exc:
        raise KeyError(f"Unknown operator_id: {operator_id}") from exc


def get_applicable_operators(item: Item) -> list[ErrorOperator]:
    return [
        op
        for op_id, op in sorted(_REGISTRY.items())
        if op_id in item.allowed_operator_ids and op.preconditions(item.solution_trace, item)
    ]


def registered_operator_ids() -> list[str]:
    return sorted(_REGISTRY)


def register_default_operators() -> None:
    """Register all built-in MVP operators, idempotently."""

    from respondent_lab.mechanisms.math_operators import MATH_OPERATORS
    from respondent_lab.mechanisms.physics_operators import PHYSICS_OPERATORS

    for op in [*MATH_OPERATORS, *PHYSICS_OPERATORS]:
        if op.operator_id not in _REGISTRY:
            register_operator(op)
