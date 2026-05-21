# Codex Implementation Prompt：Mechanism-Invariant DG MVP Foundation

你将进入一个 Python research repo。请基于工作区内的以下文件进行实现：

- `idea.md`
- `Plan.md`
- `docs/leakage_prevention_protocol.md`
- `docs/mechanism_metric_contracts.md`
- `docs/operator_library_spec.md`
- `schemas/item_schema.json`
- `schemas/solution_trace_schema.json`
- `schemas/error_operator_schema.json`
- `schemas/final_output_schema.json`
- `configs/mechanism_only.yaml`

## 0. 最高优先级约束

这是一个科研 MVP，不是普通应用开发。请优先保证：

1. **可复现**：所有 scoring 和 filtering 必须 deterministic，除非显式传入 random seed；
2. **防泄露**：`mechanism_only` 模式下，任何生成端 payload、prompt、output、intermediate artifact 都不得包含 forbidden fields；
3. **fail-fast**：不要 silent fallback，不要把 stub 或 mock 结果混入正式实验；
4. **formal-first**：LLM 只能 proposal，不得作为 truth verifier；
5. **数据人工准备**：不要自动下载、筛选、生成或改写数据。研究者会手动提供 `data/mechanism_toy_50.jsonl`。

## 1. 本轮实现范围

本轮不要试图一口气搭完整实验链路。请优先实现 Week 1 + Week 2 的基础设施，并为 Week 3 metrics 留好接口。

### 必须实现

```text
src/respondent_lab/audit/leakage_guard.py
src/respondent_lab/schemas/items.py
src/respondent_lab/schemas/traces.py
src/respondent_lab/schemas/verification.py
src/respondent_lab/mechanisms/base.py
src/respondent_lab/mechanisms/operator_registry.py
src/respondent_lab/mechanisms/math_operators.py
src/respondent_lab/mechanisms/physics_operators.py
src/respondent_lab/mechanisms/trace_executor.py
src/respondent_lab/verifiers/equivalence.py
src/respondent_lab/verifiers/symbolic_verifier.py
src/respondent_lab/verifiers/numeric_verifier.py
src/respondent_lab/verifiers/unit_verifier.py
src/respondent_lab/verifiers/formal_verifier.py
src/respondent_lab/io/load_items.py
scripts/validate_mechanism_dataset.py
tests/test_leakage_guard.py
tests/test_item_schema.py
tests/test_operator_registry.py
tests/test_math_operators.py
tests/test_physics_operators.py
tests/test_trace_executor.py
tests/test_formal_verifier.py
```

如果 repo 已有相近模块，请尽量兼容现有目录结构，但不要破坏旧 pipeline。可以新增 `mechanism_*` 命名模块避免冲突。

## 2. Config：mechanism_only

读取 `configs/mechanism_only.yaml`。至少支持：

```yaml
generation_mode: mechanism_only
fail_fast: true
forbidden_fields:
  - human_response_dist
  - distractors
  - original_options
  - original_distractors
  - seed_candidates
  - top_seed_candidates
  - distractor_meta.seed_candidates
  - item_stats.student_choice
  - student_choice
  - response_distribution
  - choice_distribution
required_leakage_audit_fields:
  - used_human_response_dist
  - used_seed_candidates
  - used_original_distractors
  - forbidden_key_scan_passed
  - canary_scan_passed
```

## 3. Leakage Guard

实现：

```python
class LeakageError(RuntimeError):
    pass

FORBIDDEN_KEYS = {...}

CANARY_PATTERNS = [
    "CANARY_DO_NOT_USE",
    "ORIGINAL_DISTRACTOR_CANARY",
]

def scan_forbidden_keys(obj: Any, forbidden_keys: set[str] | None = None) -> list[str]:
    """Recursively scan dict/list/string objects for forbidden key names or paths."""


def assert_no_leakage_payload(payload: Mapping[str, Any], forbidden_keys: set[str] | None = None) -> None:
    """Raise LeakageError if forbidden keys or canary strings are found."""


def build_leakage_audit(payload: Mapping[str, Any]) -> dict[str, bool | list[str]]:
    """Return audit metadata with used_* flags and scan pass flags."""
```

要求：

- 支持 nested dict path，例如 `distractor_meta.seed_candidates`；
- 同时扫描 key 和 string values；
- 对 prompt text 也可扫描；
- 在 `mechanism_only` 下一旦发现 forbidden fields，直接 raise；
- 测试覆盖 nested dict、list、string、canary。

## 4. Schemas / Dataclasses

请用 `pydantic` 或 standard dataclass + validation。优先 pydantic；若项目未安装 pydantic，则使用 dataclass 并提供手写 validator。

核心类型：

```python
AnswerObject
Item
TraceStep
SolutionTrace
WrongTrace
ErrorOperatorSpec
VerificationReport
FinalCandidateOutput
FinalItemOutput
```

### Item 最小字段

```python
item_id: str
subject: Literal["math", "physics"]
domain: str
question: str
correct_answer: AnswerObject
answer_type: Literal["numeric", "formula", "unit", "vector", "answer_set", "conceptual"]
givens: list[dict]
constraints: list[dict]
solution_trace: SolutionTrace
allowed_operator_ids: list[str]
counterfactual_transforms: list[str]
leakage_flags: dict[str, bool]
```

在 `Item.validate_mechanism_only()` 中检查：

- required fields 不为空；
- forbidden fields 不存在；
- `leakage_flags.original_distractors_removed == True`；
- `leakage_flags.human_response_dist_removed == True`；
- `leakage_flags.seed_candidates_removed == True`；
- solution_trace 至少 2 步；
- `allowed_operator_ids` 至少 1 个。

## 5. Operator Library

实现统一基类：

```python
class ErrorOperator(Protocol):
    operator_id: str
    subject: str
    domain: str
    description: str

    def preconditions(self, trace: SolutionTrace, item: Item) -> bool: ...
    def apply(self, trace: SolutionTrace, item: Item) -> WrongTrace: ...
    def verify(self, wrong_trace: WrongTrace, item: Item) -> VerificationReport: ...
```

实现 registry：

```python
register_operator(op: ErrorOperator) -> None
get_operator(operator_id: str) -> ErrorOperator
get_applicable_operators(item: Item) -> list[ErrorOperator]
```

### 数学 operators，本轮至少实现可测试版本

1. `ALG_SIGN_MOVE`
2. `ALG_DISTRIBUTIVE_DROP`
3. `ALG_ILLEGAL_CANCEL`
4. `ALG_SQRT_SIGN_DROP`
5. `CALC_CHAIN_RULE_DROP`

可以先支持 canonical patterns，不要过度泛化。示例：

- linear equation `a*x + b = c`；
- distributive expression `a*(b*x + c)`；
- rational expression `(a*x + b)/a`；
- square equation `(x-a)**2 = k`；
- derivative expression `(a*x+b)**n`。

### 物理 operators，本轮至少实现可测试版本

1. `PHY_UNIT_CONVERSION`
2. `PHY_VECTOR_SIGN`
3. `PHY_SCALAR_VECTOR_CONFUSION`
4. `PHY_FORMULA_DOMAIN_MISUSE`
5. `PHY_CELSIUS_KELVIN_CONFUSION`

可以先基于 structured givens / trace metadata 执行，不必解析任意自然语言。

## 6. Trace Executor

实现：

```python
def execute_wrong_trace(wrong_trace: WrongTrace, item: Item) -> AnswerObject:
    """Execute or extract final answer from a WrongTrace."""


def check_trace_executable(wrong_trace: WrongTrace, item: Item, operator: ErrorOperator) -> VerificationReport:
    """Verify unique divergence step and post-divergence executability."""
```

MVP 允许每个 `TraceStep` 包含：

```python
step_id: int
expr: str
operation: str
result: str | None
operator_id: str | None
is_divergence: bool
metadata: dict
```

要求：

- divergence step 必须唯一；
- final step 必须包含 `derived_answer` 或可解析 answer；
- `operator_id` 与应用 operator 一致；
- verification report 记录失败原因。

## 7. Formal Verifier

实现：

```python
def equivalent(a: AnswerObject, b: AnswerObject, *, tolerance: float = 1e-6) -> bool

def is_incorrect(candidate: AnswerObject, correct: AnswerObject) -> bool

def is_unique(candidate: AnswerObject, correct: AnswerObject, existing: Sequence[AnswerObject]) -> bool
```

类型要求：

- numeric：float tolerance；
- formula：SymPy simplify；
- unit：如果安装 `pint`，用 Pint；否则提供 graceful explicit error，并在 tests 中 mock；
- vector：逐分量等价；
- answer_set：集合等价。

注意：

- 不要把 dimensionally invalid 一概视为好 distractor；只返回 verification result，由上层 ranking 决定；
- 不要用 LLM 判断 correctness。

## 8. Dataset Validation CLI

实现：

```bash
python scripts/validate_mechanism_dataset.py --input data/mechanism_toy_50.jsonl --config configs/mechanism_only.yaml --out outputs/validation_report.json
```

输出：

```json
{
  "n_items": 50,
  "schema_pass": 50,
  "leakage_pass": 50,
  "failed_items": [],
  "operator_coverage": {
    "ALG_SIGN_MOVE": 8,
    "PHY_UNIT_CONVERSION": 4
  }
}
```

如果数据文件不存在，不要自动生成；打印清晰错误：

```text
Data file not found. Manual data preparation is required. See data/README_manual_data_prep.md.
```

## 9. Tests

请写 pytest。最低覆盖：

- forbidden key scan：flat, nested, dotted path, list, canary string；
- item schema：valid item, missing correct_answer, missing trace, forbidden key；
- operator registry：register/get/applicable；
- math operators：每个 operator 至少 1 positive + 1 negative precondition；
- physics operators：每个 operator 至少 1 positive + 1 negative precondition；
- trace executor：unique divergence pass, zero divergence fail, multiple divergence fail；
- verifier：numeric, symbolic, answer_set；unit 若 pint 不可用则 skip。

## 10. Coding Style

- Python 3.10+；
- 类型标注；
- 清晰异常；
- 不使用网络；
- 不自动下载数据；
- 不在 tests 中调用真实 LLM；
- 不引入大型依赖；
- 如果新增依赖，更新 `requirements.txt` 或 `pyproject.toml`；
- 不破坏已有 pipeline。

## 11. Deliverables

完成后请输出：

1. 变更文件列表；
2. 如何运行 tests；
3. 如何运行 dataset validation；
4. 当前未实现但已留接口的模块；
5. 任何与 `Plan.md` 不一致的地方。

## 12. 严禁事项

- 不要创建或伪造 `data/mechanism_toy_50.jsonl` 正式数据；
- 不要把原始 distractors、student responses、seed candidates 作为 generation input；
- 不要把 LLM judge 作为 correctness verifier；
- 不要 silent fallback；
- 不要输出看起来成功但实际使用 stub 的实验结果；
- 不要宣称实现了完整 psychometric validation。
