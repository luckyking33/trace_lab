from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from leakage_guard import LeakageError, assert_no_leakage_payload
from models import MechanismReadyItem, ValidationIssue, ValidationResponse
from path_security import PathSecurityError, safe_existing_or_new_jsonl


ANSWER_TYPES = {
    "numeric",
    "formula",
    "unit_quantity",
    "vector",
    "finite_set",
    "conceptual_binary",
}

MODIFICATION_LEVELS = {
    "original_clean",
    "numeric_perturbation",
    "paraphrased",
    "structure_preserved",
    "manual_rewrite",
}

CURRICULUM_LEVELS = {
    "elementary",
    "middle_school",
    "high_school",
    "undergraduate_intro",
    "advanced",
}

REQUIRED_TOP_LEVEL = [
    "item_id",
    "source_dataset",
    "subject",
    "domain",
    "question_clean",
    "correct_answer",
    "answer_type",
    "construct",
    "solution_trace",
    "valid_answer_set",
    "allowed_operator_ids",
    "counterfactual_transforms",
    "leakage_flags",
    "quality_control",
]

REQUIRED_QC_FLAGS = [
    "manual_checked",
    "answer_verified",
    "trace_verified",
    "operator_applicability_checked",
    "counterfactual_ready",
]


class OutputValidator:
    def __init__(self, repo_root: Path, forbidden_keys: set[str]) -> None:
        self.repo_root = repo_root
        self.forbidden_keys = forbidden_keys

    def validate(self, payload: dict[str, Any], output_path: str | None = None) -> ValidationResponse:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        try:
            item = MechanismReadyItem.model_validate(payload)
        except ValidationError as exc:
            for err in exc.errors():
                path = ".".join(str(part) for part in err.get("loc", [])) or "<root>"
                errors.append(issue("error", path, err.get("msg", "Invalid value")))
            item = None

        for field in REQUIRED_TOP_LEVEL:
            value = payload.get(field)
            if value in (None, "", [], {}):
                errors.append(issue("error", field, f"{field} is required."))

        construct = payload.get("construct") or {}
        if not isinstance(construct, dict) or not str(construct.get("primary", "")).strip():
            errors.append(issue("error", "construct.primary", "construct.primary is required."))

        trace = payload.get("solution_trace") or []
        if not isinstance(trace, list):
            errors.append(issue("error", "solution_trace", "solution_trace must be a list."))
        else:
            if len(trace) < 3:
                errors.append(issue("error", "solution_trace", "solution_trace must contain at least 3 steps."))
            step_ids = [step.get("step_id") for step in trace if isinstance(step, dict)]
            expected = list(range(1, len(step_ids) + 1))
            if step_ids != expected:
                errors.append(
                    issue("error", "solution_trace.step_id", f"step_id values must be consecutive: {expected}.")
                )

        allowed_operator_ids = payload.get("allowed_operator_ids") or []
        if not isinstance(allowed_operator_ids, list) or len([op for op in allowed_operator_ids if str(op).strip()]) < 3:
            errors.append(
                issue("error", "allowed_operator_ids", "At least 3 allowed_operator_ids are required.")
            )

        transforms = payload.get("counterfactual_transforms") or []
        if not isinstance(transforms, list) or len(transforms) < 3:
            errors.append(
                issue("error", "counterfactual_transforms", "At least 3 counterfactual_transforms are required.")
            )

        valid_answer_set = payload.get("valid_answer_set") or {}
        if not isinstance(valid_answer_set, dict) or not str(valid_answer_set.get("type", "")).strip():
            errors.append(issue("error", "valid_answer_set.type", "valid_answer_set.type is required."))

        answer_type = str(payload.get("answer_type", ""))
        if answer_type and answer_type not in ANSWER_TYPES:
            errors.append(issue("error", "answer_type", f"answer_type must be one of {sorted(ANSWER_TYPES)}."))

        modification_level = str(payload.get("modification_level", ""))
        if modification_level and modification_level not in MODIFICATION_LEVELS:
            errors.append(
                issue("error", "modification_level", f"modification_level must be one of {sorted(MODIFICATION_LEVELS)}.")
            )

        curriculum_level = str(payload.get("curriculum_level", ""))
        if curriculum_level and curriculum_level not in CURRICULUM_LEVELS:
            errors.append(
                issue("error", "curriculum_level", f"curriculum_level must be one of {sorted(CURRICULUM_LEVELS)}.")
            )

        errors.extend(self._validate_leakage_flags(payload))
        errors.extend(self._validate_quality_control(payload))

        try:
            assert_no_leakage_payload(payload, self.forbidden_keys)
        except LeakageError as exc:
            errors.append(issue("error", "leakage", str(exc)))

        if output_path is not None:
            try:
                safe_existing_or_new_jsonl(output_path, self.repo_root)
            except PathSecurityError as exc:
                errors.append(issue("error", "output_path", str(exc)))

        return ValidationResponse(valid=not errors, errors=errors, warnings=warnings)

    def validate_for_append(self, payload: dict[str, Any], output_path: str) -> ValidationResponse:
        return self.validate(payload, output_path)

    def _validate_leakage_flags(self, payload: dict[str, Any]) -> list[ValidationIssue]:
        flags = payload.get("leakage_flags") or {}
        errors: list[ValidationIssue] = []
        if not isinstance(flags, dict):
            return [issue("error", "leakage_flags", "leakage_flags must be an object.")]
        required = {
            "used_original_distractors": False,
            "used_human_response_dist": False,
            "used_seed_candidates": False,
            "original_options_removed": True,
        }
        for key, expected in required.items():
            if flags.get(key) is not expected:
                errors.append(issue("error", f"leakage_flags.{key}", f"Must be {str(expected).lower()}."))
        return errors

    def _validate_quality_control(self, payload: dict[str, Any]) -> list[ValidationIssue]:
        qc = payload.get("quality_control") or {}
        errors: list[ValidationIssue] = []
        if not isinstance(qc, dict):
            return [issue("error", "quality_control", "quality_control must be an object.")]
        for key in REQUIRED_QC_FLAGS:
            if qc.get(key) is not True:
                errors.append(issue("error", f"quality_control.{key}", "Must be true before append."))
        return errors


def issue(severity: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(severity=severity, path=path, message=message)

