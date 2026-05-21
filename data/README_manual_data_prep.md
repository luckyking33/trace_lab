# Manual Data Preparation Guide

数据准备由研究者人工完成。Codex 不负责下载、筛选、改写或生成正式数据。

---

## 1. Target File

请最终准备：

```text
data/mechanism_toy_50.jsonl
```

每行一个 item，必须符合：

```text
schemas/item_schema.json
```

---

## 2. Required Dataset Composition

```text
30 math items
20 physics items
```

每题要求：

- text-only；
- single target answer；
- correct answer 可验证；
- solution trace 3–8 步；
- 至少 1 个 allowed_operator_id，建议 3 个；
- 至少 3 类 counterfactual transforms；
- leakage flags 全部 true。

---

## 3. Do Not Include

严禁在 `mechanism_toy_50.jsonl` 中包含：

```text
human_response_dist
distractors
original_options
original_distractors
seed_candidates
top_seed_candidates
student_choice
response_distribution
choice_distribution
```

---

## 4. Template

参见：

```text
data/mechanism_toy_50.template.jsonl
```

它只是模板，不是正式数据。
