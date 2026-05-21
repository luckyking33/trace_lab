# Optional LLM Prompt：Ambiguity Auxiliary Judge

This is a secondary signal. It is not a formal verifier.

## Task

Given a question, correct answer, and candidate distractor, identify whether the candidate may be ambiguous, accidentally correct, or stylistically revealing.

## Output JSON

```json
{
  "ambiguity_risk": 0.0,
  "style_leakage_risk": 0.0,
  "possible_reasons": [],
  "requires_human_review": false
}
```

Scoring range: 0.0 low risk, 1.0 high risk.
