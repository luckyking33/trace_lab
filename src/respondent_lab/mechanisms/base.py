"""Shared error-operator interfaces."""

from __future__ import annotations

from typing import Protocol

from respondent_lab.schemas.items import Item
from respondent_lab.schemas.traces import SolutionTrace, WrongTrace
from respondent_lab.schemas.verification import VerificationReport


class ErrorOperator(Protocol):
    """Protocol implemented by deterministic error operators."""

    operator_id: str
    subject: str
    domain: str
    description: str

    def preconditions(self, trace: SolutionTrace, item: Item) -> bool:
        """Return whether this operator can be applied."""

    def apply(self, trace: SolutionTrace, item: Item) -> WrongTrace:
        """Return wrong trace with exactly one divergence step."""

    def verify(self, wrong_trace: WrongTrace, item: Item) -> VerificationReport:
        """Check incorrectness, uniqueness, trace executability, and operator match."""
