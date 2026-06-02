# Explorer A reuse logic report

工作目录：`D:\Desktop\DG\trace_lab\mechanism_invariant_dg_workspace\mechanism_invariant_dg_workspace`

任务附件已读：`C:\Users\20197\.codex\attachments\af566545-f343-4e20-813d-c7e066d076db\pasted-text.txt`

## 结论摘要

Baseline Evaluator v0 可以复用现有的答案归一化、答案等价判定、证书审计 CSV 语义、MEV v1 gate 语义、CEI pair audit 语义和 slate signature metrics。最稳妥的 v0 实现应把 evaluator 限定为评分器：生成侧不得读取 certificate bank、manual wrong traces、manual distractor answers、CEI records 或 CEI source_wrong_answer。

self certificate validation 的底层代码存在，但不建议在 Baseline Evaluator v0 默认接入。除非生成输出已经提供结构化 `operator_id` 与 `wrong_solution_trace`，且 evaluator 传入的是完整、已归一化、无泄漏的 item record，否则应设置 `self_mev_v1 = None` 并记录 `self_validation_not_implemented`。

## 可复用模块与用途

### 数据加载与归一化

- `src/respondent_lab/io/math_dataset_loader.py`
  - `load_jsonl(path) -> list[dict]`：读取 JSONL 原始 dict，适合 baseline runner 读取 item 与 generated outputs 的相同风格。
  - `load_and_normalize_math_items(path) -> list[dict]`：加载并调用 `normalize_item_record`；不会因为 negative controls 的 `allowed_operator_ids=[]` 直接拒绝。
  - `split_by_item_role(records)`：按 `item_role` 分组。

- `src/respondent_lab/io/normalization.py`
  - `normalize_answer_type(raw_type)`：把 `symbolic -> formula`，`finite_set/set_numeric/set_symbolic/set_condition -> answer_set`。
  - `strip_latex_wrappers(text)`：处理常见 LaTeX wrapper、`\frac{}`、`\sqrt{}`、`^`、隐式乘法等。
  - `normalize_answer_object(answer)`：接收 dict `{type, value}`，归一化 type/value，并在 `metadata` 保留 `raw_value`、`original_answer_type`、`latex_normalized`。
  - `normalize_trace_steps(steps)`：归一化 trace 中 `expr/result/metadata.derived_answer`，并把 `metadata.error_operator_id` 或 `metadata.operator_id` 提升为 `operator_id` 与 `is_divergence=True`。
  - `normalize_item_record(record)`：归一化 item 的 `correct_answer`、`distractor_answer`、`wrong_solution_trace`、`distractor_set` 等。

Baseline GeneratedCandidate 的 `answer` 若是 string，需要先用 item 的 `answer_type` 或 `correct_answer.type` 包装成 `{"type": item_answer_type, "value": raw}`，再调用 `normalize_answer_object`。现有归一化函数本身不直接接受裸 string 作为 answer object。

### 答案等价判定

- `src/respondent_lab/certificates/validation.py`
  - `answer_equivalent(left: dict, right: dict) -> tuple[bool, bool]`
  - 这是 baseline known certificate matching 最适合复用的 API，因为它返回 `(equivalent, parse_failure)`，正好支持附件要求的 `parse_fallback=true`。
  - 支持：
    - `numeric` / `formula`：用 SymPy parse/simplify，数值差值 tolerance `1e-6`，失败时退到 `_string_key`。
    - `answer_set`：把值 canonicalize 后排序，要求元素个数和集合内容一致；元素解析失败时退到字符串 key。
    - 其他 type：字符串 key 比较，并标记 parse fallback。
  - 注意：它要求输入是 dict answer object；裸 string 应由 evaluator 自己先 coerce。

- `src/respondent_lab/verifiers/equivalence.py`
  - `equivalent(a, b, tolerance=1e-6) -> bool`
  - `is_incorrect(candidate, correct)`、`is_unique(candidate, correct, existing)`
  - 支持 `numeric`、`formula`、`unit`、`vector`、`answer_set`、`conceptual`，并允许 numeric/formula 交叉比较。
  - 风险：不报告 parse fallback；部分解析失败会抛异常；`answer_set` 假设 `value` 可迭代，若 value 是字符串可能被拆成字符。baseline 需要 parse fallback 语义时不要直接只用这个 API。

- `src/respondent_lab/verifiers/numeric_verifier.py`
  - `numeric_equivalent` 基于 SymPy `sympify`/`N` 转 float，布尔值显式拒绝。

- `src/respondent_lab/verifiers/symbolic_verifier.py`
  - `symbolic_equivalent` 用 `simplify(expr_a - expr_b) == 0`。
  - 只适合表达式等价，不是完整方程/不等式/条件集合判定器。

- `src/respondent_lab/verifiers/unit_verifier.py`
  - `unit_equivalent` 使用 Pint；当前证书验证 `SUPPORTED_ANSWER_TYPES` 不包含 unit，但 formal verifier 支持 unit。

### 证书抽取、验证、MEV

- `src/respondent_lab/certificates/extraction.py`
  - `extract_certificates(record)`：从 `distractor_answer + wrong_solution_trace` 或 `distractor_set[]` 抽取证书 dict。
  - 证书字段包括 `item_id`、`certificate_id`、`applied_operator_ids`、`candidate_answer`、`wrong_solution_trace`、`is_composite`。
  - baseline gold oracle 可以直接从 audit CSV 读 candidate_answer；若需要回到源 item 找完整 trace，可用这个函数构建 lookup。

- `src/respondent_lab/certificates/validation.py`
  - `validate_certificate(record, certificate)`：完整证书验证入口。
  - 关键 gates：candidate present、wrong trace present、supported answer type、single/composite operator、divergence count、operator match、derived answer match、incorrectness、formal verifier trace executability。
  - `SUPPORTED_ANSWER_TYPES = {"numeric", "formula", "answer_set"}`。
  - composite certificate 在 v0 中 deferred：`composite_deferred=True`，`trace_executable_lite=False`。
  - 单 operator 且 supported answer type 时，会通过 registry 调用 operator 的 formal verifier；失败时保留 notes 并退到 lite executability。

- `src/respondent_lab/metrics/mechanistic_validity.py`
  - `compute_mev_lite(validation)`：所有 `MEV_COMPONENTS` 为真才是 1.0。
  - `compute_mev_v1(validation_record)`：MEV v1 gate 产品乘 locality。composite/deferred 返回 `mev_v1=None, mev_status="deferred_composite"`；单 operator exactly one divergence 且所有 gate 通过才 `mev_v1=1.0, mev_status="validated"`。
  - Baseline certificate bank 应按 `validation_status == validated` 且 `mev_status == validated` 或 `mev_v1 == 1.0` 过滤。

### CEI

- `src/respondent_lab/counterfactual/cei_pairs.py`
  - `load_cei_pairs(path)`：读取 manually curated CEI JSONL；缺文件会 raise，并明确 “CEI-readiness labels are not CEI”。baseline `load_cei_pair_audit` 不应复用这个缺文件即失败的语义。
  - `validate_cei_pair(pair, source_certificate_lookup=None)`：验证 transformed certificate、answer mapping、source certificate status，并输出 `cei_pair_pass`。
  - `_mapped_source_answer` 支持 `identity`、`variable_substitution`、`explicit_expected`。

- `scripts/run_math_cei_pairs.py`
  - 输出 `cei_pair_audit.csv` 和 `cei_summary.json`。
  - `cei_pair_audit.csv` 字段：`source_certificate_id`、`operator_id`、`transform_type`、`same_operator`、`transformed_certificate_mev_v1`、`answer_mapping_pass`、`source_certificate_status`、`cei_pair_pass`、`notes`。
  - Baseline certificate bank 可按 `source_certificate_id` 聚合：`cei_score = pass_count / total_count`，`cei_pair_count = total_count`。

- 当前实际 CEI audit 路径是 `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv`，不是附件示例里的 `outputs/math_cei_v1/cei_pair_audit.csv`。实现 CLI 时要允许用户传任意路径，缺文件时继续并标记 `cei_status="missing"`。

### slate metrics

- `src/respondent_lab/metrics/diagnostic_separability.py`
  - `operator_signature(applied_operator_ids)`
  - `operator_coverage(allowed_operator_ids, signatures)`
  - `redundancy(signatures)`
  - `mean_pairwise_signature_distance(signatures)`：Jaccard distance over operator id sets。
  - `compute_signature_metrics(allowed_operator_ids, certificates)`

- `src/respondent_lab/metrics/mechanism_dv.py`
  - `compute_slate_mdv_lite(record, certificates, certificate_validations)`：现有 MDV-lite 公式是 `mean_candidate_mev_lite + 0.3 * coverage + 0.2 * distance - 0.2 * redundancy`。
  - Baseline slate metrics 可复用公式和 helper，但 denominator 应改成 “certificate bank for item 的 unique operator_ids”，不是原 item `allowed_operator_ids`，以满足附件要求。

### leakage guard

- `src/respondent_lab/audit/leakage_guard.py`
  - `FORBIDDEN_KEYS`：`human_response_dist`、`distractors`、`original_options`、`original_distractors`、`seed_candidates`、`top_seed_candidates`、`distractor_meta.seed_candidates`、`item_stats.student_choice`、`student_choice`、`response_distribution`、`choice_distribution`。
  - `assert_no_leakage_payload(payload)`：发现 forbidden key 或 canary 直接 raise。
  - `build_leakage_audit(payload)`：生成 `used_*` 与 scan pass flags。
  - Baseline runner 可用它校验 `visible_input_hash` 对应的 visible payload 不含禁区字段。

## 候选答案 vs 正确答案 / 证书答案的等价判定建议

### 输入形态

已有逻辑原生支持 dict answer object：

```json
{"type": "numeric|formula|answer_set|unit|vector|conceptual", "value": "..."}
```

裸 string 不应直接传给 `answer_equivalent`。Baseline evaluator 应：

1. 从 item record 取 `answer_type`，缺失时取 `correct_answer.type`。
2. 若 generated answer 是 string，包装成 `{"type": item_answer_type, "value": string}`。
3. 若 generated answer 是 dict 且含 `type`/`value`，直接 `normalize_answer_object`。
4. 若 generated answer dict 不含 `type`/`value`，标记 `parse_success=False`。

### 正确答案 incorrectness

推荐用 `certificates.validation.answer_equivalent(candidate_answer, correct_answer)`。

- equivalent 为 true：`incorrectness=False`，最终状态应是 `invalid_equivalent_to_correct`。
- equivalent 为 false：`incorrectness=True`。
- parse_failure 为 true：保留 `parse_fallback=true` 到 notes；这不是 hard failure，但信心低。

### known certificate matching

对同一 `item_id` 的 certificate bank rows，逐个比较：

```python
equivalent, parse_fallback = answer_equivalent(generated_normalized_answer, bank_row["candidate_answer"])
```

第一个或最高优先级匹配可返回 `matched_certificate_id`、`matched_operator_ids`、`matched_mev_v1`、`matched_cei_score`、`matched_mdv_v1`。如果多个证书答案等价，应记录 duplicate ambiguity 或全部 matched ids；当前附件只要求单个 `matched_certificate_id`，实现上可取稳定排序后的第一个。

### string / dict / set / symbolic 支持边界

- string：需要 evaluator 自己 coerce；归一化后可走 SymPy 或 string fallback。
- dict `{type,value}`：支持，是主路径。
- symbolic/formula：支持表达式等价，如 `x + x` vs `2*x`。
- numeric：支持分数、小数、SymPy 可解析表达式。
- answer_set：`answer_equivalent` 支持无序精确集合等价；元素可 numeric/symbolic/string fallback。
- set_condition：会被归一化为 `answer_set`，但当前不是真正的条件集合解析器；如果 value 是 `x\in...` 字符串，可能只能 string fallback。
- unit/vector/conceptual：formal verifier 支持；certificate validation 的 `answer_equivalent` 对非 numeric/formula/answer_set 基本走字符串 fallback。当前 math certificate audit 不以 unit/vector 为主。

实际审计中有 1 条 validated certificate `parse_failure=true`：`MATH_SUP_TRANS_004_D1`，answer_set value 是 `x\in\mathbb{R}\setminus\{-2\}`，notes 为 `answer equivalence used string fallback`。如果 “warnings only records” 被解释为 `parse_failure=true` 的证书，certificate bank 应排除它；否则至少要把 parse fallback 带入 notes，避免把 string-only match 当成强 symbolic certification。

## certificate bank 实现上下文

当前 `outputs/math_certificate_audit_v0/certificate_audit.csv` 有：

- total rows: 53
- `validation_status`: 47 validated, 6 deferred_composite
- `mev_status`: 47 validated, 6 deferred_composite
- `is_composite`: 47 false, 6 true
- candidate answer types: formula 19, numeric 17, answer_set 17
- parse_failure: 52 false, 1 true

构建 bank 时建议：

- 读取 CSV cell 时对 bool 用 lowercase string：`"true"`/`"false"`。
- `candidate_answer` 和 `applied_operator_ids` 是 JSON string，需要 `json.loads`。
- 过滤条件：
  - `validation_status == "validated"`
  - `mev_status == "validated"` 或 `float(mev_v1) == 1.0`
  - `is_composite` false
  - `len(applied_operator_ids) == 1`
  - 可选/建议：若严格执行 “warnings only records” 排除，则排除 `parse_failure == "true"`。
- `normalized_answer_type` 可从 `candidate_answer["type"]` 派生；certificate audit CSV 本身没有这一列。
- `operator_signature` 可用 `"+" .join(operator_ids)` 或复用 `diagnostic_separability.operator_signature` 后序列化。
- `validation_scope` 固定为 `single_operator_single_divergence`，与 dataset summary 的 `validated_scope` 一致。

CEI aggregation：

- 当前 `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv` 有 20 rows，全为 `cei_pair_pass=true`，覆盖 10 个 source certificates，每个 2 个 pair。
- 聚合 key 是 `source_certificate_id`。
- `cei_score = pass_count / total_count`。
- 若 CEI file 缺失或 path 是 None，bank 仍应产出，`cei_score=None`、`mdv_v1=None`、`cei_status="missing"`。
- 不要调用 `counterfactual.cei_pairs.load_cei_pairs` 来加载 audit CSV；它读的是 manual JSONL，且缺文件会失败。

## self certificate validation / MEV v1 是否复用

### 可复用的窄路径

如果未来要实现 opt-in self validation，可构造：

```python
certificate = {
    "item_id": item_record["item_id"],
    "certificate_id": f"{item_id}::{candidate_id}::self",
    "applied_operator_ids": [generated_candidate.operator_id],
    "candidate_answer": normalized_generated_answer,
    "wrong_solution_trace": generated_candidate.wrong_solution_trace,
}
validation = validate_certificate(item_record, certificate)
validation.update(compute_mev_lite(validation))
validation.update(compute_mev_v1(validation))
```

前提：

- item_record 必须包含完整机制字段：`subject/domain/question/correct_answer/answer_type/givens/constraints/solution_trace/allowed_operator_ids/counterfactual_transforms/leakage_flags`。
- `operator_id` 必须是 registry 已知 operator。
- `wrong_solution_trace` 必须是结构化 list[dict]，且 divergence step 能由 `metadata.error_operator_id` 或显式 `operator_id/is_divergence` 标出。
- 当前 v0 只验证单 operator；composite 仍 deferred。

### 为什么不建议 Baseline Evaluator v0 默认接入

- 附件明确：answer-only baselines 不应分配 self MEV。
- CoT/explanation baseline 的 free-form explanation 不能当 proof；现有 validator 需要结构化 wrong trace，不验证自然语言解释。
- generated output schema 里的 `wrong_solution_trace` 尚未由现有 schema 强约束；错误格式会导致 evaluator 混入大量 verifier unavailable notes。
- 现有 `validate_certificate` 会调用 formal operator verifier，要求 item schema、operator precondition、trace divergence 都满足现有项目假设；这不是 “评分已有输出答案” 的最低必要路径。
- v0 的核心验收是 known certificate matching、incorrectness、dedup、review queue；self validation 可作为后续机制生成方法的 gated extension。

建议 v0：

- `self_certificate_present = bool(operator_id and wrong_solution_trace)`
- `self_mev_v1 = None`
- `notes` 加 `self_validation_not_implemented`
- `final_certification_status` 不应因为 explanation 或 unvalidated trace 变成 `self_certified`。

如果实现者确实要接入 self validation，应把它做成小的内部 helper，并测试 unknown operator、malformed trace、composite trace、equivalent-to-correct、validated single-op trace 等情况。

## 信息泄漏边界

Evaluator 可以在生成完成后读取：

- item records 的 safe fields，用于 correct answer 与 visible_input_hash 校验。
- generated outputs。
- certificate audit / certificate bank。
- CEI pair audit。

生成侧不得读取或注入 prompt：

- `outputs/math_certificate_audit_v0/certificate_audit.csv`
- certificate bank
- `distractor_answer`
- `wrong_solution_trace`
- `distractor_set`
- manual `candidate_answer`
- `outputs/*cei*/cei_pair_audit.csv`
- CEI JSONL records，包括 `source_wrong_answer`、`transformed_certificate`
- `human_response_dist`、`seed_candidates`、`original_distractors`、`original_options`、response/choice distribution 等 forbidden keys

Baseline matrix 里 B1/B2/B3 的 safe input 是 `question, correct_answer, answer_type`。若扩展可见字段，应显式记录并 hash，例如 `subject/domain/context/givens/constraints/solution_trace/allowed_operator_ids` 只适合机制方法，不适合普通 answer-only baseline。

`visible_input_hash` 应只 hash 实际给生成器的 visible payload；不能 hash 包含证书、wrong traces 或 CEI 的 evaluator-side payload。

Gold oracle 脚本是 sanity check，不是真 baseline。它可以读 certificate audit，但输出和 summary 必须标记 oracle/sanity，不能用于真实 baseline claim。

## 测试约定观察

- 测试框架：pytest；`pyproject.toml` 设置 `pythonpath = ["src"]`、`testpaths = ["tests"]`。
- fixture：`tests/conftest.py` 提供 `payload_factory`，产出最小机制 item。
- CLI 测试风格：
  - 使用 `tmp_path` 写入临时 JSONL/CSV。
  - 用 `subprocess.run([sys.executable, str(SCRIPT), ...], capture_output=True)` 调脚本。
  - 断言 returncode、输出文件存在、JSON/CSV 关键字段。
- 脚本输出 CSV bool convention：`_csv_cell` 把 bool 写成 lowercase `"true"`/`"false"`。
- 现有 runner tests 不跑长任务；用极小 fixture。
- CEI generation tests 用 `importlib.util.spec_from_file_location` 导入脚本模块，并通过 fake chat function 避免真实 LLM。
- 审计语义测试明确：
  - deferred composite 不算 hard failure。
  - `dataset_summary.validated_scope == "single_operator_single_divergence"`。
  - missing CEI pairs file 对 CEI runner 是清晰失败；但 Baseline Evaluator 的 CEI audit 缺失需求相反，应继续运行。
- formal verifier tests 覆盖：
  - numeric fraction vs decimal
  - symbolic `x + x` vs `2*x`
  - unordered answer_set
  - unit via Pint
  - vector
  - incorrectness and uniqueness
- 建议新增 baseline tests 延续这些模式：
  - `tests/test_certificate_bank.py`
  - `tests/test_generated_outputs.py`
  - `tests/test_baseline_evaluator.py`
  - `tests/test_evaluate_baseline_outputs_runner.py`
  - runner 测试用 `tmp_path` 创建最小 audit CSV、generated JSONL、items JSONL，不依赖完整 outputs。

## 主要实现风险

- 当前仓库没有 `src/respondent_lab/evaluation/`，也没有 `scripts/evaluate_baseline_outputs.py` / `scripts/make_gold_oracle_baseline.py`。
- 附件示例 `data/math_generation_items.jsonl` 当前不存在；实际主数据是 `data/mechanism_invariant_operator_45.jsonl`。
- 附件示例 `outputs/math_cei_v1/cei_pair_audit.csv` 当前不存在；实际 CEI audit 在 `outputs/math_cei_pairs_generated_v0/cei_pair_audit.csv`。
- `answer_equivalent` 和 `formal_verifier.equivalent` 语义不同；baseline known certificate matching 推荐用前者，因为它报告 parse fallback。
- 裸 string answer 必须由 evaluator coerce，否则现有 API 不保证 parse_success 语义。
- `answer_set` 的条件集合/不等式集合不是完整 symbolic set equivalence；可能只能 string fallback。
- 一条 validated certificate 依赖 string fallback。是否纳入 certificate bank 要和 “warnings only records” 的口径对齐。
- self validation 不应信任 explanation；没有结构化 trace 时必须保持 `self_mev_v1=None`。
