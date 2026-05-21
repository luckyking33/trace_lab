"""Pydantic models for manually prepared mechanism-only items."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from respondent_lab.audit.leakage_guard import assert_no_leakage_payload
from respondent_lab.schemas.traces import SolutionTrace


AnswerType = Literal["numeric", "formula", "unit", "vector", "answer_set", "conceptual"]


class AnswerObject(BaseModel):
    """Formal answer object used by deterministic verifiers."""

    model_config = ConfigDict(extra="allow")

    type: AnswerType
    value: Any
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Item(BaseModel):
    """Mechanism-only dataset item with fail-fast validation."""

    model_config = ConfigDict(extra="allow")

    item_id: str
    subject: Literal["math", "physics"]
    domain: str
    question: str
    correct_answer: AnswerObject
    answer_type: AnswerType
    givens: list[dict[str, Any]]
    constraints: list[dict[str, Any]]
    solution_trace: SolutionTrace
    allowed_operator_ids: list[str]
    counterfactual_transforms: list[str]
    leakage_flags: dict[str, bool]
    context: str | None = None
    curriculum_scope: str | None = None
    source: str | None = None

    @field_validator("solution_trace", mode="before")
    @classmethod
    def normalize_solution_trace(cls, value: Any, info: Any) -> Any:
        if isinstance(value, list):
            return {"item_id": info.data.get("item_id", ""), "steps": value}
        if isinstance(value, dict) and "steps" in value and not value.get("item_id"):
            value = dict(value)
            value["item_id"] = info.data.get("item_id", "")
        return value

    @model_validator(mode="after")
    def validate_mechanism_only(self) -> "Item":
        if not self.item_id.strip():
            raise ValueError("item_id must be non-empty")
        if not self.domain.strip():
            raise ValueError("domain must be non-empty")
        if not self.question.strip():
            raise ValueError("question must be non-empty")
        if self.correct_answer.value in (None, ""):
            raise ValueError("correct_answer.value must be non-empty")
        if len(self.solution_trace.steps) < 2:
            raise ValueError("solution_trace must contain at least 2 steps")
        if not self.solution_trace.item_id:
            self.solution_trace.item_id = self.item_id
        if not self.allowed_operator_ids:
            raise ValueError("allowed_operator_ids must contain at least 1 operator")

        required_flags = {
            "original_distractors_removed",
            "human_response_dist_removed",
            "seed_candidates_removed",
        }
        missing = required_flags - set(self.leakage_flags)
        if missing:
            raise ValueError(f"leakage_flags missing required fields: {sorted(missing)}")
        for flag in sorted(required_flags):
            if self.leakage_flags.get(flag) is not True:
                raise ValueError(f"leakage_flags.{flag} must be true")

        assert_no_leakage_payload(self.model_dump(mode="json"))
        return self
