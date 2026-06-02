# Worker 2 Handoff: Candidate Evaluator and Slate Metrics

## Scope

You own these files:

- `src/respondent_lab/evaluation/baseline_evaluator.py`
- `src/respondent_lab/evaluation/slate_metrics.py`

Do not edit certificate bank/schema files, scripts, or tests unless explicitly asked later.

## Required Reading

- `communication_between_me_and_myagents/TASK-SPEC.md`
- `communication_between_me_and_myagents/ORCHESTRATION.md`
- `src/respondent_lab/certificates/validation.py`
- `src/respondent_lab/verifiers/equivalence.py`
- `src/respondent_lab/io/normalization.py`
- Existing tests for certificate validation and MEV.

## Expected Interfaces From Worker 1

You may assume:

- Generated candidates have fields `candidate_id`, `answer`, `explanation`, `error_label`, `operator_id`, `wrong_solution_trace`, `metadata`.
- `normalize_generated_candidate(candidate, item_answer_type=None)` returns a dict with normalized answer, raw answer, parse success/failure notes, and a stable answer key if practical.
- Certificate bank records contain fields listed in `TASK-SPEC.md`.

If Worker 1 is not finished, write code defensively against dataclass objects and plain dicts.

## Implementation Requirements

Create:

- `evaluate_generated_candidate(item_record, generated_candidate, certificate_bank_for_item, correct_answer) -> dict`
- `evaluate_generated_item(item_record, generated_output, certificate_bank_for_item) -> dict`
- `compute_slate_metrics(candidate_eval_records, certificate_bank_for_item) -> dict`

Candidate logic:

- Determine parse success and normalized answer.
- Determine incorrectness against `correct_answer`.
- Match known certificates for the same item by formal/symbolic/set equivalence where possible.
- If equivalence parse fails, use normalized string fallback and record `parse_fallback=true`.
- `self_certificate_present` is true only when candidate has both `operator_id` and `wrong_solution_trace`.
- For v0, do not trust explanation. If self validation is not safely implemented, set `self_mev_v1 = None` and note `self_validation_not_implemented`.
- Duplicate status should be assigned at item/slate level so later duplicates become `invalid_duplicate`.
- Final statuses exactly match the task spec.

Slate metrics:

- Compute all fields listed in `TASK-SPEC.md`.
- Operator coverage denominator is unique operator IDs available in the certificate bank for that item.
- Pairwise signature distance uses Jaccard distance over matched operator signatures.
- If MDV is unavailable because CEI is missing, set `mdv_status = "cei_missing"`, include `mean_mev_v1_certified_only`, and do not pretend MDV exists.

## Constraints

- Do not call LLMs or network APIs.
- Do not modify datasets.
- Do not expose bank/manual traces/CEI to generated inputs.
- You are not alone in the codebase; do not revert or overwrite changes by others.

## Completion Report

Write `communication_between_me_and_myagents/worker_2_evaluator_metrics_report.md` with:

- Files changed.
- Matching/equivalence approach.
- Slate metric formulas.
- Any tests you ran.
- Known limitations or assumptions.

Then final reply with only a short summary and the report path.

