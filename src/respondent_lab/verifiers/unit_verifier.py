"""Unit-bearing answer equivalence using Pint."""

from __future__ import annotations

from typing import Any

from respondent_lab.schemas.items import AnswerObject

try:
    import pint
except ImportError:  # pragma: no cover - covered only in dependency-free fallback installs.
    pint = None


class UnitVerificationError(RuntimeError):
    """Raised when unit verification is unavailable or cannot parse an answer."""


def _registry() -> Any:
    if pint is None:
        raise UnitVerificationError("pint is required for unit verification")
    return pint.UnitRegistry()


def parse_quantity(value: AnswerObject | Any) -> Any:
    ureg = _registry()
    raw = value.value if isinstance(value, AnswerObject) else value
    unit = value.unit if isinstance(value, AnswerObject) else None
    try:
        if unit:
            return float(raw) * ureg(unit)
        if isinstance(raw, str):
            return ureg.Quantity(raw)
        if isinstance(raw, (int, float)):
            raise UnitVerificationError("unit answer must include a unit")
    except UnitVerificationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise UnitVerificationError(f"unparseable unit answer: {raw} {unit or ''}".strip()) from exc
    raise UnitVerificationError(f"unsupported unit answer: {raw!r}")


def unit_equivalent(a: AnswerObject | Any, b: AnswerObject | Any, *, tolerance: float) -> bool:
    qa = parse_quantity(a)
    qb = parse_quantity(b)
    if qa.dimensionality != qb.dimensionality:
        return False
    qb_in_a_units = qb.to(qa.units)
    return abs(float(qa.magnitude) - float(qb_in_a_units.magnitude)) <= tolerance
