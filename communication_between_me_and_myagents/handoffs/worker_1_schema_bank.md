# Worker 1 Handoff: Certificate Bank and Generated Output Schema

## Scope

You own these files:

- `src/respondent_lab/evaluation/__init__.py`
- `src/respondent_lab/evaluation/certificate_bank.py`
- `src/respondent_lab/evaluation/generated_outputs.py`

Do not edit scripts or tests unless explicitly asked later. Do not edit files owned by other workers.

## Required Reading

- `communication_between_me_and_myagents/TASK-SPEC.md`
- `communication_between_me_and_myagents/ORCHESTRATION.md`
- `scripts/audit_math_certificates.py`
- `src/respondent_lab/io/normalization.py`
- `src/respondent_lab/certificates/validation.py`
- `outputs/math_certificate_audit_v0/certificate_audit.csv` header/sample
- `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv` header/sample if useful

## Implementation Requirements

Create `certificate_bank.py` with:

- `load_certificate_audit(path: str | Path) -> list[dict]`
- `load_cei_pair_audit(path: str | Path | None) -> list[dict]`
- `build_certificate_bank(certificate_audit_csv, cei_pair_audit_csv=None) -> list[dict]`
- `write_certificate_bank(bank, output_path)`

Rules:

- Include only validated single-operator non-composite certificates.
- Accept `validation_status == "validated"` and `mev_status == "validated"` or `mev_v1 == 1.0`.
- Exclude `deferred_composite`, failed rows, composite rows, warnings-only rows.
- Parse JSON CSV cells like `candidate_answer` and `applied_operator_ids`.
- Normalize `candidate_answer` with existing helpers.
- CEI missing path or `None` must not crash; set `cei_score = None`, `mdv_v1 = None`, `cei_status = "missing"`.
- If CEI exists, aggregate by `source_certificate_id` as `pass_count / total_count`, storing `cei_pair_count`.

Create `generated_outputs.py` with:

- `GeneratedCandidate`
- `GeneratedItemOutput`
- `load_generated_outputs(path) -> list[GeneratedItemOutput]`
- `normalize_generated_candidate(candidate, item_answer_type=None) -> dict`

Loader rules:

- Accept JSONL.
- Accept candidate answer as raw string or dict `{"type": ..., "value": ...}`.
- Use existing answer normalization.
- Preserve raw answer enough for CLI CSV output later.

## Constraints

- Do not call LLMs or network APIs.
- Do not modify datasets.
- Do not expose certificate bank fields as generation input.
- You are not alone in the codebase; do not revert or overwrite changes by others.

## Completion Report

Write `communication_between_me_and_myagents/worker_1_schema_bank_report.md` with:

- Files changed.
- Public API summary.
- Edge cases handled.
- Any tests you ran.
- Known limitations or assumptions.

Then final reply with only a short summary and the report path.

