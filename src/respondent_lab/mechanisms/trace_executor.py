"""Wrong-trace execution and deterministic executability checks."""

from __future__ import annotations

from typing import Any

from respondent_lab.mechanisms.base import ErrorOperator
from respondent_lab.schemas.items import AnswerObject, Item
from respondent_lab.schemas.traces import TraceStep, WrongTrace
from respondent_lab.schemas.verification import VerificationReport
from respondent_lab.verifiers.formal_verifier import equivalent, is_incorrect


class TraceExecutionError(RuntimeError):
    """Raised when a wrong trace cannot yield a formal answer object."""


def _coerce_answer(raw: Any, item: Item) -> AnswerObject:
    if isinstance(raw, AnswerObject):
        return raw
    if isinstance(raw, dict):
        return AnswerObject.model_validate(raw)
    return AnswerObject(type=item.answer_type, value=raw)


def _metadata_answer(step: TraceStep) -> Any | None:
    if "derived_answer" in step.metadata:
        return step.metadata["derived_answer"]
    if "answer" in step.metadata:
        return step.metadata["answer"]
    return None


def execute_wrong_trace(wrong_trace: WrongTrace, item: Item) -> AnswerObject:
    """Execute or extract final answer from a WrongTrace."""

    if wrong_trace.candidate_answer is not None:
        return _coerce_answer(wrong_trace.candidate_answer, item)
    if not wrong_trace.steps:
        raise TraceExecutionError("wrong_trace must contain at least one step")

    final_step = wrong_trace.steps[-1]
    metadata_answer = _metadata_answer(final_step)
    if metadata_answer is not None:
        return _coerce_answer(metadata_answer, item)
    if final_step.result not in (None, ""):
        return _coerce_answer(final_step.result, item)
    raise TraceExecutionError("final step must contain derived_answer or result")


def check_trace_executable(
    wrong_trace: WrongTrace, item: Item, operator: ErrorOperator
) -> VerificationReport:
    """Verify unique divergence step and post-divergence executability."""

    notes: list[str] = []
    divergence_steps = [step for step in wrong_trace.steps if step.is_divergence]
    divergence_step_id: int | None = None
    matches_operator = wrong_trace.operator_id == operator.operator_id

    if len(divergence_steps) != 1:
        notes.append(f"expected exactly one divergence step, found {len(divergence_steps)}")
    else:
        divergence_step = divergence_steps[0]
        divergence_step_id = divergence_step.step_id
        if divergence_step.operator_id != operator.operator_id:
            matches_operator = False
            notes.append(
                "divergence step operator_id does not match "
                f"{operator.operator_id}: {divergence_step.operator_id}"
            )

    if wrong_trace.operator_id != operator.operator_id:
        notes.append(
            f"wrong_trace.operator_id {wrong_trace.operator_id} does not match {operator.operator_id}"
        )

    derived_answer: AnswerObject | None = None
    trace_executable = len(divergence_steps) == 1 and matches_operator
    try:
        derived_answer = execute_wrong_trace(wrong_trace, item)
    except Exception as exc:  # noqa: BLE001 - report all formal extraction failures.
        trace_executable = False
        notes.append(str(exc))

    correct_equivalence = False
    incorrect = False
    if derived_answer is not None:
        try:
            correct_equivalence = equivalent(derived_answer, item.correct_answer)
            incorrect = is_incorrect(derived_answer, item.correct_answer)
        except Exception as exc:  # noqa: BLE001 - verification should be structured.
            notes.append(f"formal equivalence failed: {exc}")

    return VerificationReport(
        is_incorrect=incorrect,
        is_unique=incorrect,
        trace_executable=trace_executable,
        matches_operator=matches_operator,
        divergence_step=divergence_step_id,
        derived_answer=str(derived_answer.value) if derived_answer is not None else None,
        correct_equivalence=correct_equivalence,
        notes=notes,
    )
