# Worker 2 Evaluator Metrics Report

## Files Changed

- `src/respondent_lab/evaluation/baseline_evaluator.py`
- `src/respondent_lab/evaluation/slate_metrics.py`
- `communication_between_me_and_myagents/worker_2_evaluator_metrics_report.md`

No `__init__.py`, scripts, tests, data, outputs, or Worker 1-owned files were edited.

## Candidate Evaluation

- Added `evaluate_generated_candidate(item_record, generated_candidate, certificate_bank_for_item, correct_answer)`.
- Added `evaluate_generated_item(item_record, generated_output, certificate_bank_for_item)`.
- Inputs are defensive against plain dicts, dataclasses, and Pydantic-like objects with `model_dump()`.
- Candidate answers accept raw scalar/list values when an item answer type is available, or structured `{"type": ..., "value": ...}` answer objects.
- Item and answer normalization reuse:
  - `respondent_lab.io.normalization.normalize_item_record`
  - `respondent_lab.io.normalization.normalize_answer_object`
- Correct-answer rejection and known certificate matching reuse:
  - `respondent_lab.certificates.validation.answer_equivalent`
- If equivalence falls back to string matching, the candidate notes include `parse_fallback=true`.
- Known certificate matching is restricted to the same item when bank rows carry explicit `item_id`; it will not cross-match another item if the full bank is passed.
- Duplicate detection is slate-local and marks later equivalent parsed answers as `invalid_duplicate`.
- v0 self certificate behavior:
  - `self_certificate_present` is true only with both `operator_id`/`operator_ids` and non-empty `wrong_solution_trace`.
  - `self_mev_v1` remains `None`.
  - Notes include `self_validation_not_implemented`.
  - Explanation text is not used as proof.

Final statuses emitted:

- `known_certified`
- `self_certified` only for future validated `self_mev_v1 == 1.0`; v0 does not assign it
- `incorrect_unmatched_review`
- `invalid_equivalent_to_correct`
- `invalid_parse_failure`
- `invalid_duplicate`

## Slate Metrics

Added `compute_slate_metrics(candidate_eval_records, certificate_bank_for_item)`.

Fields computed:

- `num_candidates`
- `parse_success_count`
- `incorrect_count`
- `unique_answer_count`
- `duplicate_answer_count`
- `known_certified_count`
- `self_certified_count`
- `certified_operator_ids`
- `operator_coverage`
- `answer_redundancy`
- `operator_redundancy`
- `mean_pairwise_signature_distance`
- `mean_mdv_v1_certified_only`
- `mean_mev_v1_certified_only`
- `slate_mdv_v1_lite`
- `mdv_status`
- `notes`

Formula implemented when every certified candidate has MDV:

`slate_mdv_v1_lite = mean_mdv_v1_certified_only + 0.3 * operator_coverage + 0.2 * mean_pairwise_signature_distance - 0.2 * operator_redundancy`

Coverage denominator is the unique operator ID set available in the same-item certificate bank.

If certified candidates have missing `matched_mdv_v1`, slate MDV is not computed:

- `mdv_status = "cei_missing"`
- `slate_mdv_v1_lite = None`
- `mean_mev_v1_certified_only` is exposed as fallback context

## Checks Run

- `python -m py_compile src/respondent_lab/evaluation/baseline_evaluator.py src/respondent_lab/evaluation/slate_metrics.py`
- `uv run` inline self-check for:
  - symbolic known certificate match: `x + x` vs bank answer `2*x`
  - later duplicate marked `invalid_duplicate`
  - candidate equivalent to correct marked `invalid_equivalent_to_correct`
  - MDV formula with CEI/MDV present
- `uv run` inline self-check for CEI missing:
  - candidate remains `known_certified`
  - slate `mdv_status` is `cei_missing`
  - `slate_mdv_v1_lite` stays `None`
- `uv run --no-project` import check after Worker 1 files appeared:
  - `respondent_lab.evaluation.baseline_evaluator.evaluate_generated_item`
  - `respondent_lab.evaluation.slate_metrics.compute_slate_metrics`

Transient `.venv` and `uv.lock` created by `uv run` were removed after checks.

## Known Limitations / Assumptions

- Worker 1 modules may not exist yet; evaluator falls back to local normalization if `normalize_generated_candidate` cannot be imported or used.
- v0 does not validate self-generated traces with `validate_certificate`; this is intentional to avoid trusting explanations or malformed generated traces as proof.
- `answer_set` and unsupported answer types inherit the existing `answer_equivalent` behavior, including string fallback where current parsing cannot prove formal equivalence.
- Full `pytest` was not run in this Worker 2 pass because scripts/tests are owned by later workers and the requested scope was module-local self-checking.
