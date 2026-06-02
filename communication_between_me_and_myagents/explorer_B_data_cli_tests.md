# Explorer B data / CLI / tests investigation

Workspace:

`D:\Desktop\DG\trace_lab\mechanism_invariant_dg_workspace\mechanism_invariant_dg_workspace`

Scope:

- Read-only investigation of required Baseline Evaluator v0 formats and conventions.
- Required attachment read: `C:\Users\20197\.codex\attachments\af566545-f343-4e20-813d-c7e066d076db\pasted-text.txt`.
- No source, data, or output files were modified. This report file is the only written artifact.

## Path findings

The prompt/acceptance criteria reference these paths:

- `data/math_generation_items.jsonl`
- `outputs/math_cei_v1/cei_pair_audit.csv`

In the current workspace, both are missing.

Actual corresponding files found:

- Items: `data/mechanism_invariant_operator_45.jsonl`
- Certificate audit: `outputs/math_certificate_audit_v0/certificate_audit.csv`
- CEI audit: `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv`

This is the biggest worker/acceptance risk: any acceptance command using the prompt paths will fail unless those files are created, copied, symlinked, or the command is adjusted.

## Items JSONL format

Actual file investigated: `data/mechanism_invariant_operator_45.jsonl`.

Counts:

- 45 records.
- Item roles: `operator_unit_positive` 25, `operator_unit_negative` 10, `transfer_item` 10.
- Domains: `algebra` 35, `calculus` 10.
- Raw answer types: `numeric` 17, `symbolic` 18, `finite_set` 3, `set_numeric` 6, `set_symbolic` 1.
- Normalized answer types from the existing loader: `numeric` 17, `formula` 18, `answer_set` 10.

Union of observed raw item fields:

`allowed_operator_ids`, `answer_type`, `constraints`, `correct_answer`, `counterfactual_transforms`, `data_access_mode`, `distractor_answer`, `distractor_set`, `domain`, `givens`, `item_id`, `item_role`, `leakage_audit`, `leakage_flags`, `mechanism_note`, `negative_control_for_operator_id`, `negative_control_note`, `operator_applicability`, `question`, `solution_trace`, `source`, `subject`, `target_error_operator_id`, `target_error_operator_ids`, `wrong_solution_trace`.

Correct answer location:

- Always read the correct answer from item field `correct_answer`.
- It is a dict, usually shaped as `{"type": "...", "value": "..."}` or `{"type": "...", "value": [...]}`.
- `answer_type` gives the raw answer type. Existing normalization maps `symbolic -> formula`, `finite_set/set_numeric/set_symbolic/set_condition -> answer_set`.
- Use `respondent_lab.io.math_dataset_loader.load_and_normalize_math_items()` for item loading where possible.

Distractor/certificate source fields:

- `operator_unit_positive` records have a single `distractor_answer` and `wrong_solution_trace`.
- `transfer_item` records have `distractor_set`; each entry has `distractor_id`, `applied_operator_ids`, `answer`, `wrong_solution_trace`, and often `mechanism_note`.
- `operator_unit_negative` records have no distractor/certificate payload. They are useful for audit semantics, not certificate-bank positives.

Leakage reminder:

- `distractor_answer`, `wrong_solution_trace`, `distractor_set`, certificate audit rows, and CEI rows must not be exposed to generation inputs.
- They are acceptable for evaluator/oracle scoring only.

## `certificate_audit.csv` actual columns

Actual file: `outputs/math_certificate_audit_v0/certificate_audit.csv`.

Actual columns, in order:

1. `item_id`
2. `certificate_id`
3. `item_role`
4. `applied_operator_ids`
5. `candidate_answer`
6. `is_composite`
7. `validation_status`
8. `failure_type`
9. `deferred_reason`
10. `has_candidate_answer`
11. `has_wrong_trace`
12. `divergence_step_count`
13. `operator_match`
14. `derived_answer_present`
15. `answer_match`
16. `incorrectness`
17. `trace_executable_lite`
18. `parse_failure`
19. `mev_lite`
20. `mev_status`
21. `mev_v1`
22. `gate_candidate_present`
23. `gate_wrong_trace_present`
24. `gate_incorrectness`
25. `gate_operator_match`
26. `gate_answer_match`
27. `gate_trace_executable`
28. `locality_score`
29. `notes`

Observed counts:

- 53 rows total.
- `validation_status`: `validated` 47, `deferred_composite` 6.
- `mev_status`: `validated` 47, `deferred_composite` 6.
- `is_composite`: `false` 47, `true` 6.
- Validated single-operator/non-composite count: 47.

How to identify certificate-bank eligible rows:

- `validation_status == "validated"`.
- `is_composite` parsed as boolean false.
- `applied_operator_ids` parsed from JSON cell is a list of length 1.
- `mev_status == "validated"` or numeric `mev_v1 == 1.0`.
- Exclude `validation_status == "deferred_composite"`, failed rows, warnings-only records, and any row with composite operator list.

Important CSV cell parsing:

- `applied_operator_ids` is a JSON string cell such as `["ALG_SIGN_MOVE"]`.
- `candidate_answer` is a JSON string cell such as `{"type":"numeric","value":"19/2","metadata":...}`.
- Booleans are lowercase strings like `true` / `false`.
- `candidate_answer["type"]` is the normalized answer type for that candidate. There is no separate `normalized_answer_type` column in `certificate_audit.csv`; if needed, derive it from `candidate_answer` or join/use `item_audit.csv`.

Operator distribution among validated single-operator rows:

- `ALG_SIGN_MOVE`: 11.
- `ALG_DISTRIBUTIVE_DROP`: 11.
- `ALG_ILLEGAL_CANCEL`: 9.
- `ALG_SQRT_SIGN_DROP`: 8.
- `CALC_CHAIN_RULE_DROP`: 8.

Certificate id patterns:

- For single positive items: `ITEM_ID::certificate_1`.
- For transfer distractors: usually the `distractor_id`, for example `MATH_SUP_TRANS_001_D1`.

## CEI pair audit actual columns and aggregation

Prompt path missing: `outputs/math_cei_v1/cei_pair_audit.csv`.

Actual file investigated: `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv`.

Actual columns, in order:

1. `cei_pair_id`
2. `source_item_id`
3. `source_certificate_id`
4. `operator_id`
5. `transform_type`
6. `same_operator`
7. `transformed_certificate_mev_v1`
8. `answer_mapping_type`
9. `answer_mapping_pass`
10. `source_certificate_status`
11. `cei_pair_pass`
12. `notes`

Observed counts:

- 20 CEI rows.
- 20 rows have `cei_pair_pass == "true"`.
- 10 unique `source_certificate_id` groups.
- Every covered source certificate has 2/2 passing pairs, so covered `cei_score == 1.0`.
- Transform types: `variable_renaming` 10, `numeric_perturbation` 10.
- Operators: 4 rows each for `ALG_SIGN_MOVE`, `ALG_DISTRIBUTIVE_DROP`, `ALG_ILLEGAL_CANCEL`, `ALG_SQRT_SIGN_DROP`, `CALC_CHAIN_RULE_DROP`.

Required aggregation:

- Group rows by `source_certificate_id`.
- `pass_count = count(row where lower(cei_pair_pass) == "true")`.
- `total_count = count(rows in group)`.
- `cei_score = pass_count / total_count` when `total_count > 0`.
- `cei_pair_count = total_count`.

Implementation caution:

- CEI covers only 10 of the 47 validated single-operator certificates. For bank records without any CEI group, do not silently assign 1.0. Prefer `cei_score = None`, `cei_pair_count = 0`, and a clear CEI status such as `not_covered` or equivalent.
- If the entire CEI file path is missing, the task requires continuing with `cei_status = "missing"` and `mdv_v1 = None`.

## Existing scripts CLI and output style

Common style:

- Scripts use `argparse.ArgumentParser(description=__doc__)`.
- Path arguments use `type=Path`.
- CLI functions return integer exit codes through `main()`.
- Most scripts prepend `src` to `sys.path` using `ROOT = Path(__file__).resolve().parents[1]`.
- Output directories are created with `mkdir(parents=True, exist_ok=True)`.
- CSV writers use `csv.DictWriter(..., extrasaction="ignore")`.
- `_csv_cell` serializes booleans as lowercase strings, lists/dicts as JSON with `ensure_ascii=False, sort_keys=True`, and `None` as empty string.
- JSON summary files use pretty JSON: `ensure_ascii=False`, `indent=2`, `sort_keys=True`, trailing newline.
- JSONL files write one JSON object per line with sorted keys.

Script-specific conventions:

- `scripts/validate_mechanism_dataset.py`
  - CLI: `--input`, `--config`, `--out`.
  - Writes one JSON report.
  - Missing data returns exit code 1 and prints a clear stderr message.

- `scripts/audit_math_certificates.py`
  - CLI: `--input`, `--output-dir`.
  - Prints JSON summary to stdout.
  - Writes `dataset_summary.json`, `item_audit.csv`, `certificate_audit.csv`, `slate_audit.csv`, `failures.jsonl`, `deferred.jsonl`, `warnings.jsonl`.

- `scripts/make_cei_pair_template.py`
  - CLI: `--audit-dir`, `--output`, `--max-per-operator` default 2.
  - Reads `certificate_audit.csv` under `--audit-dir`.
  - Selects validated non-composite rows, parses `applied_operator_ids`, writes JSONL templates.
  - Prints a one-line `Wrote ...` message.

- `scripts/run_math_cei_pairs.py`
  - CLI: `--audit-dir`, `--cei-pairs`, `--output-dir`.
  - On missing CEI input, returns exit code 2 and prints a clear stderr message.
  - Prints JSON summary to stdout.
  - Writes `cei_pair_audit.csv`, `cei_summary.json`, `cei_failures.jsonl`.

- `scripts/generate_math_cei_pairs_with_llm.py`
  - CLI: `--input-data`, `--audit-dir`, `--output`, `--generation-dir`, `--max-per-operator`, `--transforms`, `--retries`, `--sleep-seconds`.
  - Function tests inject fake chat functions. Do not add real LLM calls for Baseline Evaluator v0.
  - Writes accepted JSONL to `--output` plus `generation_audit.csv`, `rejected.jsonl`, `raw_responses.jsonl` under `--generation-dir`.
  - Source certificate selection filters `validation_status == "validated"`, non-composite, `mev_v1 == 1.0`, and exactly one parsed operator id.

## Existing tests style

Pytest config:

- `pyproject.toml` has `testpaths = ["tests"]` and `pythonpath = ["src"]`.
- Optional test dependency is `pytest>=8.0`.

Naming:

- Test files are named `tests/test_*.py`.
- Test functions are named `test_*`.
- Existing runner tests use files like `test_math_certificate_audit_runner.py`, `test_cei_pairs.py`, and `test_validate_mechanism_dataset.py`.

Fixtures:

- `tests/conftest.py` defines `payload_factory`, which returns deep-copied minimal math item payloads.
- Tests commonly mutate the payload for the specific scenario.

Temporary files:

- Runner tests create JSONL/CSV fixtures under `tmp_path`.
- Output assertions use `tmp_path / "audit"` or similar output dirs.
- Do not write to repo `outputs/` in tests.

CLI runner tests:

- Use `subprocess.run([sys.executable, str(SCRIPT), ...], check=False, text=True, capture_output=True)`.
- Assert `result.returncode`, often with `result.stderr` as the assertion message.
- Assert output files exist and then parse JSON/CSV content.

Function-level tests:

- Some scripts are loaded via `importlib.util.spec_from_file_location` to test script functions directly.
- LLM-related tests use fake chat functions and local temp env fixtures.

Pytest idioms:

- `pytest.raises(...)` for expected failures.
- `pytest.mark.parametrize(...)` for operator/verifier matrix tests.
- Helpers such as `_jsonl_rows(path)` parse JSONL fixtures.

Recommended new tests for Baseline Evaluator v0:

- Keep module unit tests under `tests/test_certificate_bank.py`, `tests/test_generated_outputs.py`, `tests/test_baseline_evaluator.py`.
- Keep CLI test under `tests/test_evaluate_baseline_outputs_runner.py`.
- Use tiny temp fixture CSV/JSONL files rather than repo outputs.
- For the gold oracle sanity path, generate a small fixture oracle from temp certificate audit and item files, then evaluate it through the CLI.

## Baseline Evaluator output fields from the task attachment

The new runner should create:

- `candidate_eval.csv`
- `slate_eval.csv`
- `method_summary.json`
- `review_queue.jsonl`
- `invalid_candidates.jsonl`

Required `candidate_eval.csv` columns:

`run_id`, `method`, `item_id`, `candidate_id`, `raw_answer`, `normalized_answer`, `parse_success`, `incorrectness`, `duplicate_within_slate`, `known_certificate_match`, `matched_certificate_id`, `matched_operator_ids`, `matched_mev_v1`, `matched_cei_score`, `matched_mdv_v1`, `self_certificate_present`, `self_mev_v1`, `final_certification_status`, `notes`.

Required `slate_eval.csv` columns:

`run_id`, `method`, `item_id`, `num_candidates`, `parse_success_count`, `incorrect_count`, `unique_answer_count`, `duplicate_answer_count`, `known_certified_count`, `self_certified_count`, `certified_operator_ids`, `operator_coverage`, `answer_redundancy`, `operator_redundancy`, `mean_pairwise_signature_distance`, `mean_mdv_v1_certified_only`, `slate_mdv_v1_lite`, `mdv_status`, `notes`.

Required `method_summary.json` fields:

`run_id`, `method`, `num_items`, `num_candidates`, `parse_success_rate`, `incorrectness_rate`, `unique_answer_rate`, `known_certificate_match_rate`, `self_certificate_rate`, `self_mev_v1_mean`, `matched_mev_v1_mean`, `matched_cei_score_mean`, `matched_mdv_v1_mean`, `mean_operator_coverage`, `mean_slate_mdv_v1_lite`, `review_queue_count`, `invalid_candidate_count`, `cei_status`.

Queue semantics:

- `review_queue.jsonl`: candidates where `incorrectness == true`, `known_certificate_match == false`, and self certificate is absent or not passing.
- `invalid_candidates.jsonl`: parse failures, answers equivalent to correct answer, and duplicates.

## Implementation reminders and risks

1. Path mismatch is real.
   The current repo lacks `data/math_generation_items.jsonl` and `outputs/math_cei_v1/cei_pair_audit.csv`. Worker should not assume those paths exist during local verification.

2. Use existing normalization/equivalence.
   Reuse `normalize_answer_object`, `load_and_normalize_math_items`, and `answer_equivalent` from existing code. They handle LaTeX wrappers, numeric/formula equivalence, answer sets, and parse fallback flags.

3. Do not compare raw CSV strings as business objects.
   Parse `candidate_answer` and `applied_operator_ids` JSON cells before filtering or matching.

4. Correct answer comes from items, not audit rows.
   Use normalized item `correct_answer` for incorrectness checks.

5. CEI partial coverage must be explicit.
   The CEI file is present but covers only 10 source certificates. Missing CEI group per certificate is different from a failing CEI group and different from an entirely missing CEI file.

6. Composite rows are deferred, not hard failures.
   They should not enter the certificate bank or gold oracle. Existing audit semantics intentionally report `deferred_composite` with no hard failure.

7. Generated answer loader must accept strings and dicts.
   For strings, use the item normalized answer type as the default type. For dicts, accept at least `{"type": ..., "value": ...}`.

8. Explanation is not proof.
   The attachment explicitly says not to trust generated explanations as certificates. Only `operator_id` plus `wrong_solution_trace` should count as a self-certificate input, and v0 may set self validation to not implemented if reuse is not straightforward.

9. Duplicate detection should be slate-local.
   Mark duplicates within a generated item slate after answer normalization/equivalence, not by raw string only.

10. Missing CEI audit should not crash evaluator.
    The task requires continuing with `cei_status = "missing"`, `matched_cei_score = None`, `matched_mdv_v1 = None`, and `mdv_status = "cei_missing"` style reporting.

