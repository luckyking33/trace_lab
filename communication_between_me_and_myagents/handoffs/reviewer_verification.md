# Reviewer Handoff: Independent Verification

## Scope

You are the independent verification subagent. Do not implement new features. You may make only tiny test-harness or typo fixes if explicitly asked by the main agent later.

## Required Reading

- `communication_between_me_and_myagents/TASK-SPEC.md`
- `communication_between_me_and_myagents/ORCHESTRATION.md`
- All worker reports.
- New implementation and tests.

## Verification Tasks

1. Search for any LLM/API call or baseline generation prompt implementation.
2. Run `python -m pytest`.
3. Run a fixture or local smoke command for `scripts/make_gold_oracle_baseline.py` and `scripts/evaluate_baseline_outputs.py`.
4. If `data/math_generation_items.jsonl` exists, run the exact acceptance commands from `TASK-SPEC.md`. If absent, record the precise blocker and run an equivalent temp-data smoke test.
5. Inspect output summaries for:
   - gold oracle known certificate matches,
   - `matched_mev_v1_mean`,
   - no deferred composite counted as validated,
   - missing CEI behavior.

## Completion Report

Write `communication_between_me_and_myagents/reviewer_verification_report.md` with:

- Commands run.
- Exact pass/fail results.
- Any findings with file/line references.
- Final recommendation: pass, pass with caveat, or fail.

