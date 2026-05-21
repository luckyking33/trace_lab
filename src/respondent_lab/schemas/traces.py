"""Trace models for correct and wrong reasoning paths."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TraceStep(BaseModel):
    """One executable or explanatory step in a solution trace."""

    model_config = ConfigDict(extra="allow")

    step_id: int
    expr: str
    operation: str
    result: str | None = None
    operator_id: str | None = None
    is_divergence: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SolutionTrace(BaseModel):
    """Correct solution trace supplied by the manually prepared dataset."""

    model_config = ConfigDict(extra="allow")

    item_id: str = ""
    steps: list[TraceStep]

    @model_validator(mode="after")
    def validate_steps(self) -> "SolutionTrace":
        if len(self.steps) < 2:
            raise ValueError("solution_trace must contain at least 2 steps")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("solution_trace step_id values must be unique")
        return self


class WrongTrace(BaseModel):
    """Trace produced by applying exactly one error operator."""

    model_config = ConfigDict(extra="allow")

    item_id: str = ""
    operator_id: str
    steps: list[TraceStep]
    candidate_answer: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
