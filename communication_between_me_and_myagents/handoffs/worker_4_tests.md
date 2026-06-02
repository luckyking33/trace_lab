# Worker 4 Handoff: Tests and Verification

## Scope

You own these files:

- `tests/test_certificate_bank.py`
- `tests/test_generated_outputs.py`
- `tests/test_baseline_evaluator.py`
- `tests/test_evaluate_baseline_outputs_runner.py`

Do not edit implementation files unless explicitly asked later. If tests reveal a bug, document it in your report for the main agent or relevant worker.

## Required Reading

- `communication_between_me_and_myagents/TASK-SPEC.md`
- `communication_between_me_and_myagents/ORCHESTRATION.md`
- Worker reports when available.
- Existing `tests/conftest.py`.
- Existing runner tests such as `tests/test_math_certificate_audit_runner.py` and `tests/test_cei_pairs.py`.

## Test Requirements

Cover at least:

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

Use `tmp_path` fixture for all generated files. Do not depend on absent `data/math_generation_items.jsonl`.

## Constraints

- Do not call LLMs or network APIs.
- Do not modify source datasets.
- You are not alone in the codebase; do not revert or overwrite changes by others.

## Completion Report

Write `communication_between_me_and_myagents/worker_4_tests_report.md` with:

- Files changed.
- Test cases added.
- Test command(s) run and result.
- Any implementation defects found.

Then final reply with only a short summary and the report path.

