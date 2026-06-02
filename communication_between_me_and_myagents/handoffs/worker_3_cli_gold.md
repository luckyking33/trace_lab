# Worker 3 Handoff: CLI Runner and Gold Oracle

## Scope

You own these files:

- `scripts/evaluate_baseline_outputs.py`
- `scripts/make_gold_oracle_baseline.py`

Do not edit evaluation modules or tests unless explicitly asked later.

## Required Reading

- `communication_between_me_and_myagents/TASK-SPEC.md`
- `communication_between_me_and_myagents/ORCHESTRATION.md`
- `scripts/audit_math_certificates.py`
- `scripts/run_math_cei_pairs.py`
- `src/respondent_lab/io/math_dataset_loader.py`
- `src/respondent_lab/io/load_items.py`

## Expected Interfaces

From evaluation package:

- `build_certificate_bank(certificate_audit_csv, cei_pair_audit_csv=None)`
- `load_generated_outputs(path)`
- `evaluate_generated_item(item_record, generated_output, certificate_bank_for_item)`
- `compute_slate_metrics(candidate_eval_records, certificate_bank_for_item)`

If exact return shapes differ, adapt only your scripts after integration.

## Implementation Requirements

`scripts/evaluate_baseline_outputs.py`:

- Accept args exactly:
  - `--items`
  - `--certificate-audit`
  - `--cei-audit`
  - `--generated`
  - `--output-dir`
- Add `src` to `sys.path` like existing scripts.
- Load item records as normalized dicts. Prefer `load_and_normalize_math_items` if compatible.
- Build bank and group by `item_id`.
- Load generated outputs and evaluate each generated item.
- Write:
  - `candidate_eval.csv`
  - `slate_eval.csv`
  - `method_summary.json`
  - `review_queue.jsonl`
  - `invalid_candidates.jsonl`
- Use exact columns from the source goal text.
- If `--cei-audit` path is missing, continue and report `cei_status = "missing"`.
- Review queue includes incorrect unmatched candidates whose self MEV is not passing.
- Invalid candidates include parse failures, equivalent-to-correct answers, and duplicates.

`scripts/make_gold_oracle_baseline.py`:

- Accept args exactly:
  - `--certificate-audit`
  - `--items`
  - `--output`
  - `--max-candidates-per-item`
- For each item, select up to N validated certificate answers from audit CSV.
- Write GeneratedItemOutput-compatible JSONL.
- This is a sanity oracle, not a real baseline.

## Constraints

- Do not call LLMs or network APIs.
- Do not modify datasets.
- Do not hard-code the absent local `data/math_generation_items.jsonl`.
- You are not alone in the codebase; do not revert or overwrite changes by others.

## Completion Report

Write `communication_between_me_and_myagents/worker_3_cli_gold_report.md` with:

- Files changed.
- CLI behavior.
- Output files and columns.
- Any smoke tests you ran.
- Known limitations or assumptions.

Then final reply with only a short summary and the report path.

