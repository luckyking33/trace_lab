# Worker 3 CLI / Gold Oracle Report

## Files Changed

- `scripts/evaluate_baseline_outputs.py`
- `scripts/make_gold_oracle_baseline.py`
- `communication_between_me_and_myagents/worker_3_cli_gold_report.md`

No `src`, `tests`, `data`, `outputs`, or other worker report files were edited.

## CLI Runner Behavior

`scripts/evaluate_baseline_outputs.py` accepts:

- `--items`
- `--certificate-audit`
- `--cei-audit` (optional; missing flag or missing file continues with CEI marked missing)
- `--generated`
- `--output-dir`

The runner:

- Loads normalized item records with `load_and_normalize_math_items`.
- Builds the certificate bank with `build_certificate_bank`.
- Loads generated JSONL outputs with `load_generated_outputs`.
- Evaluates each generated slate with `evaluate_generated_item`.
- Groups certificate-bank rows by `item_id`.
- Fails clearly when generated outputs reference an unknown `item_id`.
- Keeps CEI missing as a valid evaluator mode and writes `cei_status = "missing"` in `method_summary.json`; row-level notes include `cei_status=missing` or `matched_cei_status=missing`.

## Runner Outputs

The runner writes five files under `--output-dir`:

- `candidate_eval.csv`
- `slate_eval.csv`
- `method_summary.json`
- `review_queue.jsonl`
- `invalid_candidates.jsonl`

`candidate_eval.csv` columns match TASK-SPEC:

`run_id`, `method`, `item_id`, `candidate_id`, `raw_answer`, `normalized_answer`, `parse_success`, `incorrectness`, `duplicate_within_slate`, `known_certificate_match`, `matched_certificate_id`, `matched_operator_ids`, `matched_mev_v1`, `matched_cei_score`, `matched_mdv_v1`, `self_certificate_present`, `self_mev_v1`, `final_certification_status`, `notes`.

`slate_eval.csv` columns match TASK-SPEC:

`run_id`, `method`, `item_id`, `num_candidates`, `parse_success_count`, `incorrect_count`, `unique_answer_count`, `duplicate_answer_count`, `known_certified_count`, `self_certified_count`, `certified_operator_ids`, `operator_coverage`, `answer_redundancy`, `operator_redundancy`, `mean_pairwise_signature_distance`, `mean_mdv_v1_certified_only`, `slate_mdv_v1_lite`, `mdv_status`, `notes`.

`method_summary.json` includes the required summary fields:

`run_id`, `method`, `num_items`, `num_candidates`, `parse_success_rate`, `incorrectness_rate`, `unique_answer_rate`, `known_certificate_match_rate`, `self_certificate_rate`, `self_mev_v1_mean`, `matched_mev_v1_mean`, `matched_cei_score_mean`, `matched_mdv_v1_mean`, `mean_operator_coverage`, `mean_slate_mdv_v1_lite`, `review_queue_count`, `invalid_candidate_count`, `cei_status`.

## Gold Oracle Behavior

`scripts/make_gold_oracle_baseline.py` accepts:

- `--certificate-audit`
- `--items`
- `--output`
- `--max-candidates-per-item`

The script builds the same validated certificate bank and, for each item, writes up to N generated-output-compatible candidates using only validated single-operator, non-composite bank answers. Output rows are marked with:

- `method = "gold_oracle_sanity"`
- `metadata.oracle_sanity_check = true`
- `metadata.not_real_baseline = true`
- candidate metadata containing the source certificate id and operator ids

This is only an evaluator sanity oracle, not a real baseline.

## Smoke Tests Run

- `python -m py_compile scripts/evaluate_baseline_outputs.py scripts/make_gold_oracle_baseline.py`
- Temporary gold-oracle + evaluator run using:
  - `data/mechanism_invariant_operator_45.jsonl`
  - `outputs/math_certificate_audit_v0/certificate_audit.csv`
  - a deliberately missing CEI audit path under `%TEMP%`
  - output directory under `%TEMP%`
- Result from missing-CEI smoke:
  - generated oracle candidates: 47
  - evaluator output files: all five files written
  - `known_certificate_match_rate = 1.0`
  - `matched_mev_v1_mean = 1.0`
  - `cei_status = "missing"`
  - `matched_cei_score_mean = null`
  - `matched_mdv_v1_mean = null`
- Temporary smoke omitting `--cei-audit` entirely also passed with `cei_status = "missing"` and `known_certificate_match_rate = 1.0`.
- Full test suite run in an isolated dependency environment:
  - `uv run --no-project --with sympy --with pydantic --with pint --with PyYAML --with jsonschema --with pytest python -m pytest`
  - Result: `74 passed`

## Known Limitations / Assumptions

- Plain system `python` in this environment lacks `sympy`; an initial direct script smoke failed at import time before evaluator logic ran. The project declares `sympy` in `pyproject.toml`, and the isolated `uv run --no-project --with ...` checks passed.
- The prompt example paths `data/math_generation_items.jsonl` and `outputs/math_cei_v1/cei_pair_audit.csv` are still absent locally. The scripts do not hard-code these paths and accept user-supplied paths.
- The runner imports evaluator and slate logic from concrete modules instead of relying on `respondent_lab.evaluation.__init__`, because Worker 1's package init does not re-export Worker 2 APIs.
- The runner does not assign `self_mev_v1`; it preserves Worker 2's v0 behavior that answer-only or unvalidated traces are not self-certified.
