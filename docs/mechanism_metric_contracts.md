# Mechanism Metric Contracts

本文档定义 Mechanism-Invariant DG MVP 中所有自动指标的输入、输出、硬约束和解释边界。

---

## 1. Common Objects

### Item

题目对象，必须包含：

```text
item_id, subject, domain, question, correct_answer, answer_type,
givens, constraints, solution_trace, allowed_operator_ids,
counterfactual_transforms, leakage_flags
```

### Candidate

候选干扰项对象，必须包含：

```text
candidate_id, item_id, answer_object, option_text,
operator_id, wrong_trace, verification_report
```

### Slate

同一题目的 distractor set：

```text
S = {d_1, d_2, ..., d_m}
```

默认 m = 3。

---

## 2. Hard Gates

以下指标是 hard gate，任何失败都应阻止候选项进入最终 slate：

| Gate | 定义 | 失败后处理 |
|---|---|---|
| SchemaValid | item/candidate 满足 schema | reject |
| NoLeakage | 无 forbidden fields / canary | reject + raise in mechanism_only |
| Incorrectness | candidate 不等价于 correct answer | reject |
| Uniqueness | candidate 不等价于 correct，也不等价于其他 distractors | reject |
| TraceExecutable | wrong trace 可执行且 divergence step 唯一 | reject or low-rank, 由实验模式决定 |
| OperatorMatch | divergence step 匹配 operator_id | reject |

正式主实验建议：`TraceExecutable` 和 `OperatorMatch` 也作为 hard gate。

---

## 3. MEV：Mechanistic Error Validity

### 3.1 Definition

\[
\mathrm{MEV}(d|x)=
I_{incorrect}(d)
\cdot I_{trace}(d,e,\pi^*)
\cdot I_{local}(e)
\cdot \exp(-\lambda \Delta_{trace})
\]

### 3.2 Inputs

```text
item: Item
candidate: Candidate
operator: ErrorOperator
correct_trace: SolutionTrace
wrong_trace: WrongTrace
verification_report: VerificationReport
```

### 3.3 Output

```json
{
  "mev": 0.0,
  "incorrect": true,
  "trace_executable": true,
  "operator_match": true,
  "locality_score": 0.95,
  "trace_edit_distance": 1,
  "lambda": 0.2
}
```

### 3.4 Notes

- MEV 不衡量“学生是否会选”；
- MEV 不使用原始 distractors；
- MEV 不使用 historical response distribution；
- trace edit distance 可以先用 divergence step count 的简化近似。

---

## 4. CEI：Counterfactual Error Invariance

### 4.1 Definition

\[
\mathrm{CEI}(d,e,x)=
\frac{1}{K}\sum_{k=1}^{K}
\mathbb{I}[Eq(G_e(T_k(x)),\tau_k(G_e(x)))]
\]

### 4.2 Inputs

```text
item: Item
operator: ErrorOperator
transforms: list[CounterfactualTransform]
equivalence_checker: Callable
```

### 4.3 Output

```json
{
  "cei": 0.75,
  "transform_results": [
    {"transform": "variable_renaming", "passed": true},
    {"transform": "numeric_perturbation", "passed": true},
    {"transform": "unit_scale", "passed": false},
    {"transform": "controlled_paraphrase", "passed": true}
  ]
}
```

### 4.4 Notes

- 不允许用字符串相等；
- controlled paraphrase 可由 LLM 生成，但 equivalence 必须 formal；
- 若某 transform 不适用，应标记 `not_applicable`，不要计入 denominator。

---

## 5. MDS：Minimax Diagnostic Separability

### 5.1 Definition

\[
\mathrm{MDS}(S)=\min_{z_a\neq z_b}D(P(Y|z_a,S),P(Y|z_b,S))
\]

### 5.2 MVP choice model

在 mechanism-only setting 中：

```text
z_e = latent profile corresponding to error operator e
P(Y=j | z_e, S) is induced by operator-distractor matching
```

可使用 deterministic matching：

```text
P(Y=j|z_e,S)=1 if d_j matches e best, else 0
```

或 softmax matching：

```text
P(Y=j|z_e,S)=softmax(eta * match(e, d_j))
```

### 5.3 Output

```json
{
  "mds": 0.67,
  "distance": "total_variation",
  "operator_profiles": ["ALG_SIGN_MOVE", "ALG_DISTRIBUTIVE_DROP", "ALG_ILLEGAL_CANCEL"],
  "min_pair": ["ALG_SIGN_MOVE", "ALG_ILLEGAL_CANCEL"]
}
```

### 5.4 Notes

- MDS 不使用真实错误机制先验 \(P(z)\)；
- 若两个 distractors 对应同一 operator，MDS 通常下降；
- MDS 是 slate-level 指标，不适合单 candidate。

---

## 6. MDV：Mechanism-Invariant Distractor Validity

### 6.1 Candidate-level

\[
\mathrm{MDV}(d|x)=
V(d|x)\cdot \mathrm{MEV}(d|x)\cdot \mathrm{CEI}(d,e,x)
\cdot (1-\mathrm{LeakRisk})\cdot (1-\mathrm{AmbiguityRisk})
\]

### 6.2 Slate-level

\[
\mathrm{MDV}(S|x)=
\frac{1}{|S|}\sum_d \mathrm{MDV}(d|x)
+\alpha\mathrm{MDS}(S)
+\beta\mathrm{Coverage}(S)
-\gamma\mathrm{Redundancy}(S)
-\delta\mathrm{StyleLeak}(S)
\]

### 6.3 Recommended default weights

```yaml
alpha: 0.20
beta: 0.10
gamma: 0.10
delta: 0.10
lambda_trace_edit: 0.20
```

These are MVP defaults; conduct sensitivity analysis before paper submission.

---

## 7. Reporting Rules

Every final output must include:

```json
{
  "candidate_metrics": {
    "incorrectness": true,
    "uniqueness": true,
    "mev": 0.91,
    "cei": 0.75,
    "leak_risk": 0.0,
    "ambiguity_risk": 0.1,
    "mdv_candidate": 0.61
  },
  "slate_metrics": {
    "mds": 0.67,
    "coverage": 1.0,
    "redundancy": 0.0,
    "style_leak": 0.1,
    "mdv_slate": 0.72
  }
}
```

---

## 8. Claim Boundary

MDV is a mechanism-level validity metric. It is not:

- a direct estimate of student choice probability;
- an IRT parameter;
- a substitute for human pilot testing;
- a guarantee of psychometric discrimination in a real population.
