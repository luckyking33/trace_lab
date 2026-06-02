# Reviewer Verification Report

Scope: independent final verification for Baseline Evaluator v0.

Workspace:

`D:\Desktop\DG\trace_lab\mechanism_invariant_dg_workspace\mechanism_invariant_dg_workspace`

Write scope honored: this report file only. No `src`, `scripts`, `tests`, `data`, or `outputs` files were modified.

## Required Documents Read

- `communication_between_me_and_myagents/TASK-SPEC.md`
- `communication_between_me_and_myagents/ORCHESTRATION.md`
- `communication_between_me_and_myagents/explorer_A_reuse_logic.md`
- `communication_between_me_and_myagents/explorer_B_data_cli_tests.md`
- `communication_between_me_and_myagents/worker_1_schema_bank_report.md`
- `communication_between_me_and_myagents/worker_2_evaluator_metrics_report.md`
- `communication_between_me_and_myagents/worker_3_cli_gold_report.md`
- `communication_between_me_and_myagents/worker_4_tests_report.md`
- `communication_between_me_and_myagents/handoffs/reviewer_verification.md`

## LLM / API / Prompt Search

Command run:

```powershell
rg -n --glob '!apps/data_curation_ui/frontend/node_modules/**' --glob '!data/hf_home/**' --glob '!data/hf_cache/**' "(?i)(openai|anthropic|deepseek|chat.completions|responses\.create|api_key|requests\.|httpx|urllib|llm|system_prompt|generation prompt)" src/respondent_lab/evaluation scripts/evaluate_baseline_outputs.py scripts/make_gold_oracle_baseline.py tests/test_certificate_bank.py tests/test_generated_outputs.py tests/test_baseline_evaluator.py tests/test_evaluate_baseline_outputs_runner.py
```

Result: exit code 1 from `rg`, meaning no matches in the Baseline Evaluator v0 in-scope implementation and its new evaluator tests.

Broader worktree caveat:

- `scripts/generate_math_cei_pairs_with_llm.py:2` declares an OpenAI-compatible LLM API generator.
- `scripts/generate_math_cei_pairs_with_llm.py:131` defines the chat-completions HTTP call.
- `scripts/generate_math_cei_pairs_with_llm.py:402` defines `build_generation_prompt`.
- `scripts/generate_math_cei_pairs_with_llm.py:484` defines `repair_prompt_from_validation_errors`.
- `scripts/generate_math_cei_pairs_with_llm.py:533` defines `generate_cei_pairs`.
- `tests/test_generate_math_cei_pairs_with_llm.py:189` tests generation-prompt content.

I did not invoke this script, and it is outside the Baseline Evaluator deliverable files listed in `TASK-SPEC.md`. If the whole untracked worktree is considered in scope for the "no LLM/API/prompt implementation" gate, this is a scope risk to resolve outside this report. The Baseline Evaluator v0 files themselves are clean.

## Exact Acceptance Path Check

Command run:

```powershell
Test-Path -LiteralPath 'data\math_generation_items.jsonl'
Test-Path -LiteralPath 'outputs\math_cei_v1\cei_pair_audit.csv'
Test-Path -LiteralPath 'data\mechanism_invariant_operator_45.jsonl'
Test-Path -LiteralPath 'outputs\math_certificate_audit_v0\certificate_audit.csv'
```

Result:

```text
False
False
True
True
```

Blocker: exact acceptance commands from `TASK-SPEC.md` cannot be run as written because `data/math_generation_items.jsonl` is absent. The requested CEI path `outputs/math_cei_v1/cei_pair_audit.csv` is also absent, but missing CEI is an expected evaluator mode and was smoke-tested below.

## Full Test Run

Command run:

```powershell
python -m pytest
```

Result: failed before tests because system Python lacks pytest.

```text
D:\python.exe: No module named pytest
```

Fallback command run as requested:

```powershell
uv run --no-project --with sympy --with pydantic --with pint --with PyYAML --with jsonschema --with pytest python -m pytest
```

Result:

```text
80 passed in 13.50s
```

## Gold Oracle + Evaluator Smoke

Used actual local inputs and a deliberately missing CEI audit path. All outputs were written under a system temp directory, not repo `outputs/`.

Temp root:

`C:\Users\20197\AppData\Local\Temp\baseline_eval_reviewer_e51c0ad0244a49f89770b605eb1fa9d6`

Commands run:

```powershell
uv run --no-project --with sympy --with pydantic --with pint --with PyYAML --with jsonschema --with pytest python scripts/make_gold_oracle_baseline.py --certificate-audit outputs/math_certificate_audit_v0/certificate_audit.csv --items data/mechanism_invariant_operator_45.jsonl --output C:\Users\20197\AppData\Local\Temp\baseline_eval_reviewer_e51c0ad0244a49f89770b605eb1fa9d6\raw\gold_oracle_v1.jsonl --max-candidates-per-item 3

uv run --no-project --with sympy --with pydantic --with pint --with PyYAML --with jsonschema --with pytest python scripts/evaluate_baseline_outputs.py --items data/mechanism_invariant_operator_45.jsonl --certificate-audit outputs/math_certificate_audit_v0/certificate_audit.csv --cei-audit C:\Users\20197\AppData\Local\Temp\baseline_eval_reviewer_e51c0ad0244a49f89770b605eb1fa9d6\missing_cei_pair_audit.csv --generated C:\Users\20197\AppData\Local\Temp\baseline_eval_reviewer_e51c0ad0244a49f89770b605eb1fa9d6\raw\gold_oracle_v1.jsonl --output-dir C:\Users\20197\AppData\Local\Temp\baseline_eval_reviewer_e51c0ad0244a49f89770b605eb1fa9d6\eval
```

Gold oracle result:

```json
{
  "max_candidates_per_item": 3,
  "method": "gold_oracle_sanity",
  "not_real_baseline": true,
  "num_candidates": 47,
  "num_items": 45,
  "oracle_sanity_check": true,
  "run_id": "gold_oracle_v1"
}
```

Evaluator summary result:

```json
{
  "cei_status": "missing",
  "incorrectness_rate": 1.0,
  "invalid_candidate_count": 0,
  "known_certificate_match_rate": 1.0,
  "matched_cei_score_mean": null,
  "matched_mdv_v1_mean": null,
  "matched_mev_v1_mean": 1.0,
  "mean_operator_coverage": 0.7777777777777778,
  "mean_slate_mdv_v1_lite": null,
  "num_candidates": 47,
  "num_items": 45,
  "parse_success_rate": 1.0,
  "review_queue_count": 0,
  "self_certificate_rate": 0.0,
  "self_mev_v1_mean": null,
  "unique_answer_rate": 1.0
}
```

Output files present:

- `candidate_eval.csv`
- `slate_eval.csv`
- `method_summary.json`
- `review_queue.jsonl`
- `invalid_candidates.jsonl`

## Structural Verification

Read-only inline check initially failed with `ModuleNotFoundError: No module named 'respondent_lab'` because `PYTHONPATH=src` was not set for direct stdin execution under `uv run --no-project`. Reran with `PYTHONPATH=src`; result passed.

Read-only verification result:

```json
{
  "audit_deferred_composite_rows": 6,
  "audit_total_rows": 53,
  "bank_cei_status_counts": {
    "missing": 47
  },
  "bank_deferred_id_count": 0,
  "bank_rows_missing_cei": 47,
  "bank_scope_counts": {
    "single_operator_single_divergence": 47
  },
  "candidate_notes_with_missing_cei": 47,
  "oracle_candidate_count": 47,
  "oracle_deferred_id_count": 0,
  "oracle_item_rows": 45,
  "slate_mdv_status_counts": {
    "cei_missing": 35,
    "no_certified_candidates": 10
  }
}
```

Interpretation:

- The source audit contains 6 deferred/composite rows.
- The validated bank under missing CEI contains 47 rows, all `single_operator_single_divergence`.
- No deferred composite certificate id entered the bank or oracle.
- Oracle/evaluator candidate count is 47; all matched known certificates.
- Missing CEI semantics are explicit in summary (`cei_status = "missing"`), candidate notes (`matched_cei_status=missing` for 47 candidates), and slate status (`cei_missing` or `no_certified_candidates` for no-candidate slates).

## Findings

1. Path blocker: `data/math_generation_items.jsonl` is absent, so exact `TASK-SPEC.md` acceptance commands cannot run as written. Equivalent smoke using `data/mechanism_invariant_operator_45.jsonl` passed.

2. Scope caveat: the Baseline Evaluator v0 files contain no LLM/API calls or generation prompts, but the broader worktree contains LLM/prompt implementation in `scripts/generate_math_cei_pairs_with_llm.py` with references listed above. It was not executed during this review.

No Baseline Evaluator v0 implementation defect was found in the in-scope files.

## Final Recommendation

Pass with caveats.

The Baseline Evaluator v0 implementation passes full tests and equivalent gold-oracle smoke. The remaining caveats are environmental/scope-related: missing exact `data/math_generation_items.jsonl`, missing exact CEI path handled as intended, and a separate worktree LLM generation script outside the Baseline Evaluator deliverables.
