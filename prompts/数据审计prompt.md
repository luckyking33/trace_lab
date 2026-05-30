You are working in the repository:
https://github.com/luckyking33/trace_lab

Project context:
This repository implements a Mechanism-Invariant Distractor Generation / Evaluation MVP.
The goal is NOT to build a full LLM distractor generation system yet.
The immediate goal is to build a math-only certificate audit runner for a manually prepared JSONL dataset.

Dataset:
I will place a file at:
data/mechanism_invariant_operator_45.jsonl

This file contains 45 math items with mixed item roles:
- operator_unit_positive
- operator_unit_negative
- transfer_item

Important:
Do NOT modify the source dataset file.
Do NOT call any LLM.
Do NOT implement baselines in this step.
Do NOT claim real CEI unless transformed items are actually generated and verified.
This task is only for deterministic loading, normalization, leakage audit, certificate validation, and metric reporting.

Existing repository modules:
- src/respondent_lab/schemas/items.py
- src/respondent_lab/schemas/traces.py
- src/respondent_lab/schemas/verification.py
- src/respondent_lab/audit/leakage_guard.py
- src/respondent_lab/mechanisms/base.py
- src/respondent_lab/mechanisms/operator_registry.py
- src/respondent_lab/mechanisms/math_operators.py
- src/respondent_lab/mechanisms/trace_executor.py
- src/respondent_lab/verifiers/*

High-level goal:
Implement Math Certificate Audit v0.

The runner should read the 45-item JSONL file, normalize answer types and LaTeX-ish expressions, split items by role, validate leakage flags, validate manually supplied distractor certificates, and produce structured outputs.

Key design requirements:

1. Add a data normalization module

Create:
src/respondent_lab/io/normalization.py

Implement functions:

- normalize_answer_type(raw_type: str) -> tuple[str, dict]
  Mapping:
    numeric       -> numeric
    symbolic      -> formula
    finite_set    -> answer_set
    set_numeric   -> answer_set
    set_symbolic  -> answer_set
    set_condition -> answer_set
    formula       -> formula
    answer_set    -> answer_set
  Return normalized type plus metadata containing original_answer_type.

- strip_latex_wrappers(text: str) -> str
  Remove wrappers like \( ... \), convert common LaTeX constructs where possible:
    \frac{a}{b} -> (a)/(b)
    \sqrt{a} -> sqrt(a)
    \pm -> +-
  Do NOT over-engineer a perfect LaTeX parser.
  The purpose is to improve SymPy compatibility and produce an audit flag.

- normalize_answer_object(answer: dict) -> dict
  Normalize answer["type"] and clean answer["value"].
  If value is a list, normalize each element.
  Preserve original raw value in metadata.raw_value.

- normalize_trace_steps(steps: list[dict]) -> list[dict]
  Normalize:
    if step.metadata.error_operator_id exists:
        step.operator_id = that value unless already set
        step.is_divergence = true
    if step.metadata.operator_id exists:
        step.operator_id = that value unless already set
        step.is_divergence = true
  Preserve metadata.

- normalize_item_record(record: dict) -> dict
  Apply all above normalizations to:
    correct_answer
    solution_trace
    wrong_solution_trace
    distractor_answer
    distractor_set[*].answer
    distractor_set[*].wrong_solution_trace

2. Add dataset loader and splitter

Create:
src/respondent_lab/io/math_dataset_loader.py

Implement:
- load_jsonl(path: str | Path) -> list[dict]
- load_and_normalize_math_items(path: str | Path) -> list[dict]
- split_by_item_role(records) -> dict[str, list[dict]]

The loader should NOT reject negative controls just because allowed_operator_ids is empty.
The existing Item model may still be used for compatible positive/transfer records, but negative controls require a lighter validation path.

3. Add certificate extraction

Create:
src/respondent_lab/certificates/extraction.py

Define a normalized certificate record shape:

{
  "item_id": "...",
  "item_role": "...",
  "certificate_id": "...",
  "applied_operator_ids": [...],
  "candidate_answer": {...},
  "wrong_solution_trace": [...],
  "mechanism_note": "...",
  "is_composite": bool
}

Extraction rules:
- If the item has distractor_answer + wrong_solution_trace:
    create one certificate using target_error_operator_id.
- If the item has distractor_set:
    create one certificate per distractor.
- If applied_operator_ids length > 1:
    mark is_composite = true.
- If no certificate exists, return zero certificates.

4. Add deterministic certificate validation

Create:
src/respondent_lab/certificates/validation.py

Implement:
- validate_certificate(record: dict, certificate: dict) -> dict

Validation should check:
- has_candidate_answer
- has_wrong_trace
- candidate_answer_type_supported
- single_operator_certificate
- composite_certificate
- divergence_step_count
- operator_match
- derived_answer_present
- incorrectness, using existing formal verifier if possible
- unique_vs_correct; for now, uniqueness can mean not equivalent to correct answer
- answer_match: candidate answer equals derived answer, using symbolic/set equivalence where possible
- trace_executable_lite

Important:
For v0:
- Single-operator certificates should be fully validated.
- Composite certificates should not be forced through the existing WrongTrace(operator_id: str) schema.
- Composite certificates should receive structural validation and be marked:
    composite_deferred = true
  unless you implement clean support for multiple divergence steps.

Implement answer equivalence robustly:
- scalar numeric/formula: use SymPy where parseable
- answer_set: compare normalized set equality, not subset
- if parsing fails, fall back to normalized string comparison and record parse_failure=true
- A candidate answer that is a subset of the correct answer set is NOT equivalent to the correct answer set, unless the sets are equal.

5. Add MEV-lite and slate metrics

Create:
src/respondent_lab/metrics/mechanistic_validity.py
src/respondent_lab/metrics/diagnostic_separability.py
src/respondent_lab/metrics/mechanism_dv.py

Implement candidate-level:

MEV-lite:
  1.0 if:
    has_candidate_answer
    has_wrong_trace
    incorrectness == true
    operator_match == true
    answer_match == true
    trace_executable_lite == true
  else 0.0

Also return component fields.

Implement slate-level for items with distractor_set:
- operator_coverage:
    unique applied operators covered / allowed operators for item
- redundancy:
    percentage of duplicate operator signatures among distractors
- mean_pairwise_signature_distance:
    1 - Jaccard(signature_i, signature_j), averaged over pairs
- slate_mdv_lite:
    mean(candidate_mev_lite)
    + 0.3 * operator_coverage
    + 0.2 * mean_pairwise_signature_distance
    - 0.2 * redundancy

Do not implement real CEI yet.
Instead implement:
- cei_readiness:
    number of counterfactual_transforms >= 1
    and all transforms are non-empty strings

6. Add audit runner script

Create:
scripts/audit_math_certificates.py

CLI:
python scripts/audit_math_certificates.py \
  --input data/mechanism_invariant_operator_45.jsonl \
  --output-dir outputs/math_certificate_audit_v0

Outputs:
- dataset_summary.json
- item_audit.csv
- certificate_audit.csv
- slate_audit.csv
- failures.jsonl

dataset_summary.json should include:
- total_items
- items_by_role
- items_by_domain
- answer_type_raw_counts
- answer_type_normalized_counts
- total_certificates
- certificates_by_operator_signature
- single_operator_certificates
- composite_certificates
- leakage_pass_rate
- certificate_mev_lite_mean
- precondition_positive_recall
- negative_control_false_positive_rate
- transfer_item_slate_count

item_audit.csv columns:
- item_id
- item_role
- domain
- raw_answer_type
- normalized_answer_type
- allowed_operator_ids
- target_error_operator_id
- target_error_operator_ids
- negative_control_for_operator_id
- num_certificates
- leakage_pass
- schema_compatible
- cei_readiness
- notes

certificate_audit.csv columns:
- item_id
- certificate_id
- item_role
- applied_operator_ids
- is_composite
- has_candidate_answer
- has_wrong_trace
- divergence_step_count
- operator_match
- derived_answer_present
- answer_match
- incorrectness
- trace_executable_lite
- parse_failure
- mev_lite
- notes

slate_audit.csv columns:
- item_id
- num_distractors
- allowed_operator_ids
- covered_operator_ids
- operator_coverage
- redundancy
- mean_pairwise_signature_distance
- mean_candidate_mev_lite
- slate_mdv_lite
- notes

7. Add precondition audit

Use existing operator_registry.register_default_operators() and get_applicable_operators(item) where possible.

For positive items:
- If target_error_operator_id exists:
    expected applicable.
- If target_error_operator_ids exists:
    expected applicable for each listed operator.

For negative controls:
- negative_control_for_operator_id is expected NOT applicable.

Because current Item schema rejects allowed_operator_ids=[], do not force negative controls through Item. For negative controls, create a temporary copy with allowed_operator_ids = [negative_control_for_operator_id] only for checking whether the operator would fire. Record this clearly as a test-only view.

8. Add tests

Create tests:
tests/test_math_dataset_normalization.py
tests/test_certificate_extraction.py
tests/test_certificate_validation.py
tests/test_math_certificate_audit_runner.py

At minimum test:
- answer_type mapping symbolic -> formula
- set_numeric -> answer_set
- LaTeX wrapper stripping
- metadata.error_operator_id becomes step.operator_id and is_divergence=true
- negative controls do not crash loader
- distractor_set extracts multiple certificates
- composite certificate is marked deferred
- answer_set equality requires exact set equality
- runner produces all output files on a small temporary JSONL fixture

9. Keep dependencies light

The current pyproject has pydantic, jsonschema, PyYAML, sympy, pint, pytest.
Avoid adding pandas unless absolutely necessary.
Use csv/json/stdlib for reports.

10. Acceptance criteria

After implementation, these commands should work:

python -m pytest

python scripts/audit_math_certificates.py \
  --input data/mechanism_invariant_operator_45.jsonl \
  --output-dir outputs/math_certificate_audit_v0

The runner should not crash on:
- symbolic answer types
- finite_set/set_numeric/set_symbolic answer types
- negative controls with empty allowed_operator_ids
- transfer items with distractor_set
- composite applied_operator_ids
- LaTeX-wrapped values like \(6\), \frac{8}{3}, \sqrt{31}

The implementation should clearly distinguish:
- real certificate validation
- composite certificate deferred validation
- CEI-readiness
- real CEI not yet implemented