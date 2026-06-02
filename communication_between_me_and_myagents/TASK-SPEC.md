# Baseline Evaluator v0 Task Spec

## Source Goal

Primary goal text:

- `C:\Users\20197\.codex\attachments\af566545-f343-4e20-813d-c7e066d076db\pasted-text.txt`

Workspace:

- `D:\Desktop\DG\trace_lab\mechanism_invariant_dg_workspace\mechanism_invariant_dg_workspace`

## Role Contract

The main agent is the project director. It coordinates subagents, reviews code and generated outputs, maintains quality gates, and reports to the user. The main agent should not personally implement business code except for orchestration documents or exceptional integration fixes.

Subagents must communicate through files under `communication_between_me_and_myagents`. Each subagent must read this spec and its handoff file before work, then write a completion report under the same folder.

## Non-Negotiable Constraints

- Do not call any LLM.
- Do not implement baseline generation prompts.
- Do not modify the source dataset.
- Do not expose certificate bank, manual wrong traces, distractor answers, or CEI records to generation inputs.
- Build only the deterministic evaluator that can score outputs from zero-shot, CoT, DiVERT-style, and future certificate-generating methods.
- Unmatched but incorrect candidates go to a review queue, not a hard failure.
- Explanation text is never trusted as proof.
- For answer-only baselines, do not assign `self_mev_v1`.

## Existing Context Observed Locally

Existing reusable files:

- `src/respondent_lab/certificates/validation.py`
  - `answer_equivalent(left, right) -> tuple[bool, bool]` supports symbolic/set-ish equivalence and string fallback reporting.
  - `validate_certificate(record, certificate)` exists, but Baseline v0 should usually leave self validation as not implemented unless a worker proves a safe scoped reuse.
- `src/respondent_lab/io/normalization.py`
  - `normalize_answer_object`, `normalize_item_record`, and answer type mapping.
- `src/respondent_lab/verifiers/equivalence.py`
  - formal dispatchers for numeric/formula/unit/vector/answer_set/conceptual when values are `AnswerObject`/dict-like.
- `scripts/audit_math_certificates.py`
  - current CSV/JSON writer style and certificate audit columns.
- `scripts/run_math_cei_pairs.py`
  - CEI audit columns and CLI style.

Actual local files:

- `outputs/math_certificate_audit_v0/certificate_audit.csv` exists.
- `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv` exists.
- `outputs/math_cei_v1/cei_pair_audit.csv` currently does not exist.
- `data/mechanism_invariant_operator_45.jsonl` exists.
- `data/math_generation_items.jsonl` currently does not exist.

Implementation must honor the user-specified CLI paths, but should not hard-code them. Missing CEI audit must not crash. Missing items path may fail clearly because the evaluator and gold oracle require item records.

## Deliverables

Create package:

- `src/respondent_lab/evaluation/__init__.py`
- `src/respondent_lab/evaluation/certificate_bank.py`
- `src/respondent_lab/evaluation/generated_outputs.py`
- `src/respondent_lab/evaluation/baseline_evaluator.py`
- `src/respondent_lab/evaluation/slate_metrics.py`

Create scripts:

- `scripts/evaluate_baseline_outputs.py`
- `scripts/make_gold_oracle_baseline.py`

Create tests:

- `tests/test_certificate_bank.py`
- `tests/test_generated_outputs.py`
- `tests/test_baseline_evaluator.py`
- `tests/test_evaluate_baseline_outputs_runner.py`

## Required Functional Detail

### Certificate Bank

Functions:

- `load_certificate_audit(path: str | Path) -> list[dict]`
- `load_cei_pair_audit(path: str | Path | None) -> list[dict]`
- `build_certificate_bank(certificate_audit_csv, cei_pair_audit_csv=None) -> list[dict]`
- `write_certificate_bank(bank, output_path)`

Include only:

- `validation_status == "validated"`
- `mev_status == "validated"` or `mev_v1 == 1.0`
- non-composite single-operator certificates

Exclude:

- `deferred_composite`
- failed records
- warnings-only records

Each bank record:

- `item_id`
- `certificate_id`
- `candidate_answer`
- `normalized_answer_type`
- `operator_ids`
- `operator_signature`
- `mev_v1`
- `cei_score`
- `cei_pair_count`
- `mdv_v1 = mev_v1 * cei_score if cei_score exists else None`
- `validation_scope = "single_operator_single_divergence"`
- `cei_status`

If CEI is missing, continue with `cei_score = None`, `mdv_v1 = None`, and `cei_status = "missing"`.

If multiple CEI pairs exist, aggregate by `source_certificate_id` as `pass_count / total_count`, storing `cei_pair_count`.

### Generated Outputs

Use lightweight dataclasses or pydantic models:

- `GeneratedCandidate`
- `GeneratedItemOutput`

Functions:

- `load_generated_outputs(path) -> list[GeneratedItemOutput]`
- `normalize_generated_candidate(candidate, item_answer_type=None) -> dict`

Loader accepts answer as a raw string or dict `{"type": ..., "value": ...}`.

### Candidate-Level Evaluation

Functions:

- `evaluate_generated_candidate(item_record, generated_candidate, certificate_bank_for_item, correct_answer) -> dict`
- `evaluate_generated_item(item_record, generated_output, certificate_bank_for_item) -> dict`

Checks:

- parse success
- normalized answer
- incorrectness against correct answer
- known certificate match against same-item certificate bank
- matched certificate/operator/MEV/CEI/MDV fields
- self certificate presence from `operator_id` plus `wrong_solution_trace`
- self validation v0 behavior
- final status:
  - `known_certified`
  - `self_certified`
  - `incorrect_unmatched_review`
  - `invalid_equivalent_to_correct`
  - `invalid_parse_failure`
  - `invalid_duplicate`
- notes

Known match must use symbolic/set equivalence where possible. If equivalence parsing fails, fall back to normalized string comparison and record `parse_fallback=true`.

### Slate Metrics

Function:

- `compute_slate_metrics(candidate_eval_records, certificate_bank_for_item) -> dict`

Required fields:

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
- `slate_mdv_v1_lite`
- `mdv_status`
- `notes`

Formula:

`slate_mdv_v1_lite = mean_mdv_v1_certified_only + 0.3 * operator_coverage + 0.2 * mean_pairwise_signature_distance - 0.2 * operator_redundancy`

If CEI is missing and `mdv_v1` is `None`, expose fallback `mean_mev_v1_certified_only`, do not pretend MDV exists, and set `mdv_status = "cei_missing"`.

### CLI Runner

Command:

```powershell
python scripts/evaluate_baseline_outputs.py `
  --items data/math_generation_items.jsonl `
  --certificate-audit outputs/math_certificate_audit_v0/certificate_audit.csv `
  --cei-audit outputs/math_cei_v1/cei_pair_audit.csv `
  --generated outputs/baselines/raw/zero_shot_v1.jsonl `
  --output-dir outputs/baseline_eval_v0/zero_shot_v1
```

Outputs:

- `candidate_eval.csv`
- `slate_eval.csv`
- `method_summary.json`
- `review_queue.jsonl`
- `invalid_candidates.jsonl`

Column requirements are exactly as listed in the source goal text.

### Gold Oracle

Command:

```powershell
python scripts/make_gold_oracle_baseline.py `
  --certificate-audit outputs/math_certificate_audit_v0/certificate_audit.csv `
  --items data/math_generation_items.jsonl `
  --output outputs/baselines/raw/gold_oracle_v1.jsonl `
  --max-candidates-per-item 3
```

Behavior:

- For each item, select up to 3 validated certificate answers from the audit CSV.
- Write `GeneratedItemOutput` JSONL.
- This is only an evaluator sanity check, not a real baseline.

## Acceptance Commands

After implementation:

```powershell
python -m pytest
```

Then:

```powershell
python scripts/make_gold_oracle_baseline.py `
  --certificate-audit outputs/math_certificate_audit_v0/certificate_audit.csv `
  --items data/math_generation_items.jsonl `
  --output outputs/baselines/raw/gold_oracle_v1.jsonl `
  --max-candidates-per-item 3

python scripts/evaluate_baseline_outputs.py `
  --items data/math_generation_items.jsonl `
  --certificate-audit outputs/math_certificate_audit_v0/certificate_audit.csv `
  --cei-audit outputs/math_cei_v1/cei_pair_audit.csv `
  --generated outputs/baselines/raw/gold_oracle_v1.jsonl `
  --output-dir outputs/baseline_eval_v0/gold_oracle_v1
```

Expected gold oracle:

- `known_certificate_match_rate` approximately 1.0
- `matched_mev_v1_mean` approximately 1.0
- no deferred composite counted as validated

If `data/math_generation_items.jsonl` is still missing, record this as an environment/data blocker for the final acceptance command while still ensuring pytest and fixture-based runner tests pass.

## Minimum Test Requirements

1. Certificate bank excludes deferred composites.
2. Certificate bank includes validated single-operator certificates.
3. CEI aggregation computes `pass_count / total_count`.
4. Generated output loader accepts answer as string and dict.
5. Answer matching detects equivalent symbolic answers.
6. Unmatched incorrect candidate goes to review queue status.
7. Equivalent-to-correct candidate is `invalid_equivalent_to_correct`.
8. Duplicate candidates are marked duplicate.
9. Gold oracle output evaluates to `known_certificate_match = true`.
10. Missing CEI audit does not crash evaluator and sets `cei_status = missing`.

