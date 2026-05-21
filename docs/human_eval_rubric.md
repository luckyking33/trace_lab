# Expert Evaluation Rubric

本 rubric 用于评估 distractor 的机制忠实性、可执行性与教学价值。建议采用 3 位专家，分两阶段盲评。

---

## 1. Annotation Phases

### Phase 1：Option-only

专家看到：

```text
Item ID
Question
Correct answer
Candidate distractor
Target student level
```

专家不看 method、operator、wrong trace。

评分维度：

- Formal Incorrectness；
- Plausibility；
- Ambiguity Risk；
- Style Leakage；
- Pedagogical Usefulness。

### Phase 2：Trace-exposed

专家额外看到：

```text
operator_id
operator description
wrong trace
divergence step
formal verification report
```

评分维度：

- Mechanism Faithfulness；
- Trace Executability；
- Misconception Clarity。

---

## 2. Likert Scale

### 2.1 Mechanism Faithfulness

| Score | Description |
|---:|---|
| 1 | wrong trace 与 distractor 基本无关 |
| 2 | 有弱相关，但不能解释 distractor |
| 3 | 部分解释 distractor，但机制不够局部或不够自然 |
| 4 | 基本由该机制推出，仅有轻微不清晰 |
| 5 | distractor 明确由该错误机制局部、自然、可执行地产生 |

### 2.2 Trace Executability

| Score | Description |
|---:|---|
| 1 | 推理步骤断裂，无法执行 |
| 2 | 多处跳步或不合法 |
| 3 | 大体可跟随，但有关键省略 |
| 4 | 基本可执行，少量表达不严谨 |
| 5 | 每一步都可执行，divergence step 清晰 |

### 2.3 Misconception Clarity

| Score | Description |
|---:|---|
| 1 | 无法对应明确错误概念 |
| 2 | 错误概念非常泛化 |
| 3 | 可大致命名，但不够诊断性 |
| 4 | 能指向明确教学错误 |
| 5 | 可清晰命名并用于教学诊断 |

### 2.4 Pedagogical Usefulness

| Score | Description |
|---:|---|
| 1 | 不适合作为教学或诊断干扰项 |
| 2 | 价值较弱，可能太怪或太明显 |
| 3 | 有一定教学价值 |
| 4 | 有明确诊断价值 |
| 5 | 非常适合识别具体错误机制并支持反馈 |

### 2.5 Plausibility

| Score | Description |
|---:|---|
| 1 | 目标学生几乎不会选择 |
| 2 | 只有少数学生可能选择 |
| 3 | 有一定迷惑性 |
| 4 | 较可能被目标学生选择 |
| 5 | 非常自然，目标学生很可能因该机制选择 |

### 2.6 Ambiguity Risk

| Score | Description |
|---:|---|
| 1 | 无明显歧义 |
| 2 | 轻微歧义 |
| 3 | 中等歧义 |
| 4 | 高歧义 |
| 5 | 可能被解释为合理答案或多种错误机制 |

统计时 reverse-code：

```text
NonAmbiguity = 6 - AmbiguityRisk
```

### 2.7 Style Leakage

| Score | Description |
|---:|---|
| 1 | 与其他选项风格一致，无明显泄露 |
| 2 | 轻微风格线索 |
| 3 | 中等风格线索 |
| 4 | 明显格式、长度、单位或数量级线索 |
| 5 | 几乎一眼可排除 |

统计时 reverse-code：

```text
NonLeakage = 6 - StyleLeakage
```

---

## 3. Agreement and Correlation

### 3.1 Inter-rater agreement

- Binary labels：Fleiss' Kappa；
- Ordinal Likert：Krippendorff's alpha 或分箱后 Fleiss' Kappa；
- 补充：ICC。

### 3.2 MDV-expert correlation

报告：

```text
Pearson(MDV, mean Mechanism Faithfulness)
Spearman(MDV, mean Mechanism Faithfulness)
Spearman(MDV, mean Pedagogical Usefulness)
Spearman(CEI, mean Mechanism Faithfulness)
Spearman(MEV, mean Trace Executability)
```

所有相关建议提供 bootstrap 95% CI。
