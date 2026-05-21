"""Verification and output schema models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ErrorOperatorSpec(BaseModel):
    """Serializable description of an error operator."""

    model_config = ConfigDict(extra="allow")

    operator_id: str
    subject: Literal["math", "physics"]
    domain: str
    description: str
    preconditions: list[str]
    divergence_pattern: str
    verification_requirements: list[str]
    examples: list[dict[str, Any]] = Field(default_factory=list)


class VerificationReport(BaseModel):
    """Structured report emitted by formal gates."""

    is_incorrect: bool = False
    is_unique: bool = False
    trace_executable: bool = False
    matches_operator: bool = False
    dimensionally_valid: bool | None = None
    divergence_step: int | None = None
    derived_answer: str | None = None
    correct_equivalence: bool = False
    duplicate_of: str | None = None
    notes: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.is_incorrect
            and self.is_unique
            and self.trace_executable
            and self.matches_operator
        )


class FinalCandidateOutput(BaseModel):
    """Candidate-level output reserved for Week 3 metrics integration."""

    model_config = ConfigDict(extra="allow")

    candidate_id: str
    item_id: str
    answer_object: dict[str, Any]
    option_text: str
    operator_id: str
    wrong_trace: dict[str, Any]
    verification_report: VerificationReport
    candidate_metrics: dict[str, Any] = Field(default_factory=dict)


class FinalItemOutput(BaseModel):
    """Final item output with required leakage audit metadata."""

    model_config = ConfigDict(extra="allow")

    item_id: str
    method: str
    pipeline_status: Literal["all_formal_verified", "partial_verified", "failed"]
    data_access_mode: Literal["mechanism_only", "human_seeded_proxy"]
    candidates: list[FinalCandidateOutput | dict[str, Any]]
    slate_metrics: dict[str, Any]
    leakage_audit: dict[str, Any]

    @model_validator(mode="after")
    def validate_leakage_audit(self) -> "FinalItemOutput":
        required = {
            "used_human_response_dist",
            "used_seed_candidates",
            "used_original_distractors",
            "forbidden_key_scan_passed",
            "canary_scan_passed",
        }
        missing = required - set(self.leakage_audit)
        if missing:
            raise ValueError(f"leakage_audit missing required fields: {sorted(missing)}")
        return self
