# Mechanism-Invariant DG Workspace

这是一个用于快速启动 **Mechanism-Invariant Distractor Generation / Evaluation** 实验的工作区文件包。

## 文件结构

```text
idea.md                                # 研究构想整合文档
Plan.md                                # 详细实验计划
CodexPrompt.md                         # 交给 Codex 的初步高质量实现 prompt
configs/mechanism_only.yaml            # mechanism_only 配置模板
schemas/*.json                         # 数据、轨迹、operator、输出 schema
docs/mechanism_metric_contracts.md     # MEV/CEI/MDS/MDV 指标契约
docs/leakage_prevention_protocol.md    # 防泄露协议
docs/operator_library_spec.md          # 错误算子库设计
docs/human_eval_rubric.md              # 专家评估 rubric
docs/experiment_logging_contract.md    # 实验日志与输出约定
docs/paper_claims_and_boundaries.md    # 论文 claim 与边界
data/README_manual_data_prep.md        # 人工数据准备说明
data/mechanism_toy_50.template.jsonl   # 数据模板，不是正式数据
prompts/*.md                           # 可选 LLM prompt 模板
experiments/*.md / *.yaml              # baseline matrix 与 run manifest 模板
evaluation/*.csv                       # 专家标注表模板
```

## 使用顺序

1. 阅读 `idea.md`，确认研究范式和论文定位；
2. 阅读 `Plan.md`，确认 4 周执行计划；
3. 研究者人工准备 `data/mechanism_toy_50.jsonl`；
4. 将 `CodexPrompt.md` 交给 Codex，实现 Week 1 + Week 2 基础设施；
5. 使用 `docs/leakage_prevention_protocol.md` 审计所有输入、prompt、输出；
6. 用 `docs/human_eval_rubric.md` 生成专家评估包。

## 核心原则

- 生成端不读学生分布；
- 生成端不读原始 distractors；
- 生成端不读 seed candidates；
- LLM 只做 proposal，不做 truth；
- formal verifier 是 hard gate；
- 50 题 MVP 只支持 proof-of-concept，不支持完整 psychometric claim。
