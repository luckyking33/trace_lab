# Experiment Logging Contract

本文件定义所有实验运行必须记录的字段，以支持可复现、可审计和防泄露。

---

## 1. Run Manifest

每次运行必须生成：

```text
outputs/<run_id>/run_manifest.json
```

字段：

```json
{
  "run_id": "20260515_mechanism_mvp_v1",
  "timestamp": "2026-05-15T00:00:00+09:00",
  "git_commit": "...",
  "config_path": "configs/mechanism_only.yaml",
  "data_path": "data/mechanism_toy_50.jsonl",
  "generation_mode": "mechanism_only",
  "random_seed": 42,
  "methods": ["zero_shot", "divert_style", "mechanism_invariant"],
  "forbidden_key_scan_enabled": true,
  "canary_scan_enabled": true
}
```

---

## 2. Per-item Output

```json
{
  "item_id": "MATH_ALG_001",
  "method": "mechanism_invariant",
  "pipeline_status": "all_formal_verified",
  "data_access_mode": "mechanism_only",
  "candidates": [],
  "slate_metrics": {},
  "leakage_audit": {}
}
```

---

## 3. Candidate Output

```json
{
  "candidate_id": "MATH_ALG_001_D1",
  "option_text": "x = 11/3",
  "answer_object": {"type": "numeric", "value": "11/3"},
  "operator_id": "ALG_SIGN_MOVE",
  "wrong_trace": [],
  "verification": {
    "is_incorrect": true,
    "is_unique": true,
    "trace_executable": true,
    "matches_operator": true,
    "dimensionally_valid": null,
    "divergence_step": 2,
    "derived_answer": "11/3",
    "correct_equivalence": false,
    "duplicate_of": null,
    "notes": []
  },
  "metrics": {
    "mev": 0.91,
    "cei": 0.75,
    "leak_risk": 0.0,
    "ambiguity_risk": 0.1,
    "mdv_candidate": 0.61
  }
}
```

---

## 4. LLM Call Log

若使用 LLM，必须记录：

```json
{
  "call_id": "uuid",
  "item_id": "...",
  "module": "candidate_verbalizer",
  "model": "...",
  "temperature": 0.2,
  "prompt_hash": "sha256...",
  "payload_allowed_keys": ["question", "correct_answer", "answer_object"],
  "forbidden_key_scan_passed": true,
  "canary_scan_passed": true,
  "raw_output_hash": "sha256..."
}
```

不要在 public artifact 中保存可能含私密信息的完整 prompt；保存 hash 和 sanitized payload 即可。
