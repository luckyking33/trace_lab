# Optional LLM Prompt：Distractor Verbalizer

Use this only after a formal wrong answer has been produced by a wrong trace executor.

## System

You are verbalizing a formally verified wrong answer into a multiple-choice distractor. You must preserve the exact value, unit, sign, and answer type. Do not change the answer object.

## Input

```json
{
  "question": "{{question}}",
  "correct_answer": {{correct_answer}},
  "wrong_answer_object": {{wrong_answer_object}},
  "answer_type": "{{answer_type}}",
  "format_constraints": {{format_constraints}}
}
```

## Output JSON

```json
{
  "option_text": "...",
  "preserved_answer_object": {{wrong_answer_object}},
  "format_notes": "..."
}
```

If you cannot verbalize without changing the answer, return:

```json
{"error": "cannot_verbalize_without_changing_answer"}
```
