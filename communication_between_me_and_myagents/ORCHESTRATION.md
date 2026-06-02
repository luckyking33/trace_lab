# Baseline Evaluator v0 Orchestration Ledger

## Current Status

Status: complete with caveats.

Main agent role: project director, integration reviewer, quality gate owner.

## Agents

| Agent | Type | Scope | Status | Report |
| --- | --- | --- | --- | --- |
| Explorer A | explorer | Reusable validation/equivalence/MEV logic | completed | `explorer_A_reuse_logic.md` |
| Explorer B | explorer | Data formats, CLI style, tests | completed | `explorer_B_data_cli_tests.md` |
| Worker 1 | worker | Evaluation package setup, certificate bank, generated output schema | completed | `worker_1_schema_bank_report.md` |
| Worker 2 | worker | Candidate evaluator and slate metrics | completed | `worker_2_evaluator_metrics_report.md` |
| Worker 3 | worker | CLI runner and gold oracle scripts | completed | `worker_3_cli_gold_report.md` |
| Worker 4 | worker | Tests and fixture-level verification | completed | `worker_4_tests_report.md` |
| Reviewer | worker | Independent verification and acceptance commands | completed | `reviewer_verification_report.md` |

## Decisions

- Use existing deterministic equivalence/normalization helpers rather than adding a new parser.
- Keep self certificate validation as v0-not-implemented unless a worker can safely wrap existing `validate_certificate` without trusting explanations or leaking bank data.
- Treat missing CEI audit as a valid evaluator mode with `cei_status = "missing"`.
- Do not hard-code `data/math_generation_items.jsonl` because it is absent locally; scripts must accept any valid items JSONL path.
- Workers have disjoint write scopes to reduce conflicts.

## Risks

- `data/math_generation_items.jsonl` is absent locally, so final gold-oracle acceptance command may be blocked unless the user supplies or creates that file. Tests should use temporary fixture item files.
- The requested `outputs/math_cei_v1/cei_pair_audit.csv` is absent locally; implementation must continue with CEI missing. A generated CEI audit exists at `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv`.
- CSV fields store JSON values as strings; workers must parse JSON cells robustly.
- Some PowerShell output may display mojibake for Unicode; file reads/writes should use UTF-8.

## Quality Gates

1. Worker reports written under `communication_between_me_and_myagents`.
2. New code must be deterministic and contain no LLM/API calls.
3. `python -m pytest` passes.
4. Fixture-based CLI smoke test produces all five evaluator outputs.
5. If local item path exists, gold oracle command and evaluator command run and summary satisfies acceptance. If missing, record blocker precisely.

## Final Verification

- In-scope Baseline Evaluator v0 files contain no LLM/API calls or generation prompts.
- Full suite passed in dependency-provisioned environment: `80 passed`.
- Equivalent gold oracle smoke using `data/mechanism_invariant_operator_45.jsonl` produced 47 oracle candidates and evaluator `known_certificate_match_rate = 1.0`, `matched_mev_v1_mean = 1.0`, `cei_status = "missing"`.
- Exact acceptance item path `data/math_generation_items.jsonl` is absent locally, so the exact commands cannot run as written until that file exists.
- Requested CEI path `outputs/math_cei_v1/cei_pair_audit.csv` is absent locally; missing CEI behavior is implemented and verified.

## Commit/Stage Policy

The user did not ask for a commit. Do not commit automatically.
