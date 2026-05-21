# Leakage Prevention Protocol

本协议是 Mechanism-Invariant DG 实验的硬性前置条件。若生成端读取原始 distractors、学生响应分布或 seed candidates，则 no-reference / distribution-free claim 直接失效。

---

## 1. Experiment Modes

### 1.1 mechanism_only

主实验模式。

允许字段：

```text
question
context
subject
domain
correct_answer
curriculum_scope
answer_type
givens
constraints
solution_trace
allowed_operator_ids
counterfactual_transforms
```

禁止字段：

```text
human_response_dist
distractors
original_options
original_distractors
seed_candidates
top_seed_candidates
distractor_meta.seed_candidates
item_stats.student_choice
student_choice
response_distribution
choice_distribution
```

### 1.2 human_seeded_proxy

仅用于辅助分析或后验验证。

允许读取 response distribution / seed candidates，但必须在论文中声明为 proxy mode，不能用于主方法 claim。

---

## 2. Directory Isolation

建议目录：

```text
data/source_quarantine/        # 可以存放原始 MCQ，但生成脚本不得读取
data/derived_no_options/       # 只含题干、正确答案、solution trace
data/mechanism_toy_50.jsonl    # 主实验数据
audit/prompt_logs/             # LLM payload audit
audit/output_logs/             # final output audit
```

主实验脚本只允许读取：

```text
data/mechanism_toy_50.jsonl
configs/mechanism_only.yaml
schemas/*.json
```

---

## 3. Programmatic Guard

### 3.1 Forbidden key scan

所有输入 payload、LLM prompt、intermediate artifact、final output 都要递归扫描 forbidden keys。

伪代码：

```python
FORBIDDEN_KEYS = {
    "human_response_dist",
    "distractors",
    "original_options",
    "original_distractors",
    "seed_candidates",
    "top_seed_candidates",
    "distractor_meta.seed_candidates",
    "item_stats.student_choice",
    "student_choice",
    "response_distribution",
    "choice_distribution",
}

class LeakageError(RuntimeError):
    pass

def assert_no_leakage_payload(payload: dict):
    serialized = json.dumps(payload, ensure_ascii=False)
    for key in FORBIDDEN_KEYS:
        if key in serialized:
            raise LeakageError(f"Forbidden key detected: {key}")
```

### 3.2 Canary scan

在 quarantine 数据中可人工加入 canary：

```text
CANARY_DO_NOT_USE_9f3a
ORIGINAL_DISTRACTOR_CANARY
```

实验后扫描所有 prompt / output / log：

```python
def canary_scan(output_dir: Path):
    for file in output_dir.rglob("*"):
        if file.is_file():
            text = file.read_text(errors="ignore")
            if "CANARY_DO_NOT_USE" in text or "ORIGINAL_DISTRACTOR_CANARY" in text:
                raise LeakageError(f"Canary leaked in {file}")
```

---

## 4. Required Audit Metadata

每个 LLM call log：

```json
{
  "call_id": "uuid",
  "generation_mode": "mechanism_only",
  "allowed_input_keys": ["question", "correct_answer", "subject", "domain", "answer_type"],
  "forbidden_key_scan_passed": true,
  "canary_scan_passed": true,
  "prompt_hash": "sha256...",
  "model": "...",
  "temperature": 0.2,
  "timestamp": "..."
}
```

每个 final output：

```json
{
  "pipeline_status": "all_formal_verified",
  "data_access_mode": "mechanism_only",
  "leakage_audit": {
    "used_human_response_dist": false,
    "used_seed_candidates": false,
    "used_original_distractors": false,
    "forbidden_key_scan_passed": true,
    "canary_scan_passed": true
  }
}
```

---

## 5. Failure Policy

在 `mechanism_only` 下：

| Failure | Action |
|---|---|
| forbidden key detected | raise `LeakageError` |
| canary detected | raise `LeakageError` |
| missing leakage_flags | reject item |
| `original_distractors_removed=false` | reject item |
| `human_response_dist_removed=false` | reject item |
| `seed_candidates_removed=false` | reject item |
| silent fallback attempted | raise error |

---

## 6. Paper Reporting

论文中必须报告：

- 是否使用原始 distractors：No；
- 是否使用 student response distribution：No；
- 是否使用 seed candidates：No；
- 是否进行了 forbidden key scan：Yes；
- 是否进行了 canary scan：Yes；
- 是否存在 human_seeded_proxy experiment：若有，必须单独标注，不与主方法混合。
