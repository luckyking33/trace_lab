# Error Operator Library Specification

本文件定义 Mechanism-Invariant DG MVP 的错误算子库。错误算子是本项目的核心研究资产。

---

## 1. Operator Design Principles

每个 operator 必须满足：

1. **Locality**：只在正确轨迹中引入一个局部 divergence；
2. **Executability**：错误轨迹可以执行得到具体 wrong answer；
3. **Interpretability**：可以用教学语言命名；
4. **Preconditioned**：只有满足明确条件的题目才可施加；
5. **Verifiability**：错误结果可由 formal verifier 检查；
6. **Counterfactual Applicability**：至少部分题目变换后仍可施加。

---

## 2. Unified Interface

```python
class ErrorOperator:
    operator_id: str
    subject: str
    domain: str
    description: str

    def preconditions(self, trace: SolutionTrace, item: Item) -> bool:
        """Return whether this operator can be applied."""

    def apply(self, trace: SolutionTrace, item: Item) -> WrongTrace:
        """Return wrong trace with exactly one divergence step."""

    def verify(self, wrong_trace: WrongTrace, item: Item) -> VerificationReport:
        """Check incorrectness, uniqueness, trace executability, and operator match."""
```

---

## 3. Math Operators

### 3.1 ALG_SIGN_MOVE

**Description**：移项时忘记改变符号。

Canonical form：

\[
a x + b = c
\]

Correct：

\[
x = \frac{c-b}{a}
\]

Wrong：

\[
x = \frac{c+b}{a}
\]

Precondition：linear equation with additive constant.

---

### 3.2 ALG_DISTRIBUTIVE_DROP

**Description**：分配律只作用到第一项，漏乘第二项。

Canonical form：

\[
a(bx+c)
\]

Correct：

\[
abx + ac
\]

Wrong：

\[
abx + c
\]

---

### 3.3 ALG_ILLEGAL_CANCEL

**Description**：跨加法非法约分。

Examples：

\[
\frac{ax+b}{a} \rightarrow x+b
\]

or

\[
\frac{x+2}{x} \rightarrow 2
\]

---

### 3.4 ALG_SQRT_SIGN_DROP

**Description**：开平方时只保留正根。

Canonical form：

\[
(x-a)^2 = k, k>0
\]

Correct：

\[
x = a \pm \sqrt{k}
\]

Wrong：

\[
x = a + \sqrt{k}
\]

---

### 3.5 CALC_CHAIN_RULE_DROP

**Description**：复合函数求导时遗漏内函数导数。

Canonical form：

\[
\frac{d}{dx}(ax+b)^n
\]

Correct：

\[
n(ax+b)^{n-1}a
\]

Wrong：

\[
n(ax+b)^{n-1}
\]

---

## 4. Physics Operators

### 4.1 PHY_UNIT_CONVERSION

**Description**：使用数值但忘记单位换算。

Example：

```text
30 cm → wrongly treated as 30 m
```

Policy：若题目 construct 不是 unit/dimensional reasoning，则 dimensionally invalid candidates 应被标记为 high style-leak risk。

---

### 4.2 PHY_VECTOR_SIGN

**Description**：方向约定导致符号错误。

Example：

```text
Positive direction is right; acceleration is left; wrong trace uses +a instead of -a.
```

---

### 4.3 PHY_SCALAR_VECTOR_CONFUSION

**Description**：向量大小误用标量加法。

Correct：

\[
v = \sqrt{v_x^2+v_y^2}
\]

Wrong：

\[
v = v_x + v_y
\]

---

### 4.4 PHY_FORMULA_DOMAIN_MISUSE

**Description**：在不满足条件时使用公式。

Example：non-uniform motion uses average velocity formula where final velocity is required.

---

### 4.5 PHY_CELSIUS_KELVIN_CONFUSION

**Description**：在 Kelvin-based formula 中直接使用 Celsius magnitude。

Correct：

\[
T_K=T_C+273.15
\]

Wrong：

\[
T_K=T_C
\]

---

## 5. Operator Registry Rules

- operator_id 全局唯一；
- preconditions 必须 deterministic；
- apply 之后 wrong_trace 必须有 exactly one divergence step；
- apply 不能修改原始 correct trace object；
- verify 必须返回 structured report；
- unsupported pattern 应返回 `False` 或明确异常，不得 silent fallback。
