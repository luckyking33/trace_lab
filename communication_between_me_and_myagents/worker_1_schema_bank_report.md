# Worker 1 Schema / Certificate Bank Report

## Files changed

- `src/respondent_lab/evaluation/__init__.py`
- `src/respondent_lab/evaluation/certificate_bank.py`
- `src/respondent_lab/evaluation/generated_outputs.py`
- `communication_between_me_and_myagents/worker_1_schema_bank_report.md`

## Public API summary

`respondent_lab.evaluation.certificate_bank` now provides:

- `load_certificate_audit(path) -> list[dict]`
- `load_cei_pair_audit(path) -> list[dict]`
- `build_certificate_bank(certificate_audit_csv, cei_pair_audit_csv=None) -> list[dict]`
- `write_certificate_bank(bank, output_path)`

`respondent_lab.evaluation.generated_outputs` now provides:

- `GeneratedCandidate`
- `GeneratedItemOutput`
- `load_generated_outputs(path) -> list[GeneratedItemOutput]`
- `normalize_generated_candidate(candidate, item_answer_type=None) -> dict`

The package `respondent_lab.evaluation` re-exports those APIs.

## Edge cases handled

- Certificate audit JSON cells are parsed structurally for `candidate_answer` and `applied_operator_ids`.
- Candidate answers from audit rows are normalized with `normalize_answer_object`.
- Certificate bank includes only validated, non-composite, single-operator records with `mev_status == "validated"` or `mev_v1 == 1.0`.
- Validated `parse_failure == true` audit rows are retained in the certificate bank; the flag is preserved under bank record `metadata.parse_failure` for downstream parse-fallback notes.
- Missing CEI audit path or `None` does not crash bank construction; bank rows receive `cei_score = None`, `cei_pair_count = 0`, `mdv_v1 = None`, and `cei_status = "missing"`.
- Existing CEI audit rows are aggregated by `source_certificate_id` as `pass_count / total_count`.
- Certificates not covered by an existing CEI audit receive `cei_status = "not_covered"` rather than a fabricated CEI score.
- Generated output JSONL loader accepts candidate answers as raw strings or answer dicts shaped as `{"type": ..., "value": ...}`.
- Generated output loader also accepts a single-candidate JSONL row with top-level `answer`, `answer_object`, or `raw_answer`.
- `GeneratedCandidate` now covers `explanation` and `error_label`, and accepts `wrong_solution_trace=None` while normalizing it to `[]`.
- `GeneratedItemOutput` now covers `prompt_version`, `model`, and `visible_input_hash`; loader fills missing `run_id` and `method` as empty strings instead of `None`.
- Generated candidate normalization reports parse failures structurally instead of raising during evaluation helper use.
- Raw candidate answers are preserved in `normalize_generated_candidate(...)[raw_answer]` for later CSV output.

## Tests / self-checks run

- `python -m compileall -q src/respondent_lab/evaluation`
- Lightweight import and behavior self-check with `PYTHONPATH=src`:
  - Built bank from `outputs/math_certificate_audit_v0/certificate_audit.csv` with missing CEI.
  - Built bank from the same audit plus `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv`.
  - Confirmed CEI statuses included `passed` and `not_covered`.
  - Loaded temporary generated JSONL containing one raw string answer and one dict answer.
  - Normalized generated answers using item answer types.

Original self-check result:

```json
{"bank_cei_count": 46, "bank_missing_count": 46, "cei_status_counts": {"not_covered": 36, "passed": 10}}
```

Rework self-checks run:

- `python -m compileall -q src/respondent_lab/evaluation/certificate_bank.py src/respondent_lab/evaluation/generated_outputs.py`
- Lightweight import and behavior self-check with `PYTHONPATH=src`:
  - Built bank from `outputs/math_certificate_audit_v0/certificate_audit.csv` with missing CEI.
  - Confirmed missing-CEI bank count is 47.
  - Built bank from the same audit plus `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv`.
  - Confirmed actual CEI status counts are 10 `passed` and 37 `not_covered`.
  - Confirmed one validated parse-fallback certificate is retained with `metadata.parse_failure = true`.
  - Loaded temporary generated JSONL containing `run_id`, `method`, `prompt_version`, `model`, `visible_input_hash`, `explanation`, `error_label`, and `wrong_solution_trace = null`.
  - Confirmed `wrong_solution_trace = null` normalizes to `[]` and candidate normalization preserves `explanation` / `error_label`.

Rework observed self-check result:

```json
{"bank_cei_count": 47, "bank_missing_count": 47, "cei_status_counts": {"not_covered": 37, "passed": 10}, "parse_failure_retained_count": 1}
```

Additional operator-id extraction self-check:

- Fixed `_extract_operator_id` to check `operator_ids` and `applied_operator_ids` one key at a time.
- Ran `python -m compileall -q src/respondent_lab/evaluation/generated_outputs.py`.
- Ran a temporary JSONL loader check confirming `operator_ids=["ALG_SIGN_MOVE"]` produces `operator_id == "ALG_SIGN_MOVE"`.

Observed result:

```json
{"operator_id": "ALG_SIGN_MOVE", "operator_ids_extraction": "passed"}
```

## Known limitations / assumptions

- This worker did not edit scripts, tests, data, outputs, or other evaluation modules.
- `write_certificate_bank` writes JSON for `.json`, CSV for `.csv`, and JSONL for all other suffixes.
- Raw string generated answers require `item_answer_type` for the most accurate normalization; if omitted, normalization defaults to `formula` and records a note.
- Self-certificate validation is not implemented here. The schema only preserves `operator_id` and `wrong_solution_trace` and marks `self_certificate_present` for downstream evaluator logic.
