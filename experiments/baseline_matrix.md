# Baseline Matrix

| ID | Method | Input Allowed | Output | Notes |
|---|---|---|---|---|
| B1 | Zero-shot LLM DG | question, correct_answer, answer_type | 3 distractors | No seed, no student data |
| B2 | CoT LLM DG | question, correct_answer, answer_type | 3 distractors + free-form rationale | Rationale not accepted as formal trace |
| B3 | DiVERT-style | question, correct_answer, answer_type | error representation + distractors | Style baseline, not full reproduction |
| B4 | Student-Choice-Prediction-style | generated candidate pool only | ranked distractors | No empirical student data; must be labeled style/proxy |
| B5 | Current psychometric-refactor proxy | depends on safe config | distractors | Must report mode and leakage audit |
| Ours | Mechanism-Invariant DG | mechanism_only fields | wrong traces + distractors + verification | Main method |

## Fairness Rules

- Same 50 items;
- Same number of distractors per item;
- Same formal validity gate;
- Same leakage audit;
- Same expert evaluation rubric;
- Prompt hashes logged for all LLM methods.
