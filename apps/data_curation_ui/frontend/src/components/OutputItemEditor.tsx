import { useState } from "react";
import type { ReactNode } from "react";
import { buttonLabel, UiLanguage } from "../api";

export interface TraceStep {
  step_id: number;
  premise: string;
  operation: string;
  expr_before: string | null;
  expr_after: string | null;
  verifier_hint: string | null;
}

export interface MechanismItem {
  source_metadata_zh?: Record<string, string>;
  item_id: string;
  source_dataset: string;
  source_split: string;
  source_family: string;
  source_record_id: string;
  license_note: string;
  subject: string;
  domain: string;
  curriculum_level: string;
  question_clean: string;
  question_original_available: boolean;
  modification_level: string;
  correct_answer: string;
  answer_type: string;
  answer_format: { type: string; unit: string | null; precision: string | null };
  construct: { primary: string; secondary: string[] };
  givens: Array<{ symbol: string; value: string }>;
  variables: Array<{ symbol: string; role: string; domain: string }>;
  constraints: Array<{ type: string; target: string; value: string }>;
  solution_trace: TraceStep[];
  valid_answer_set: { type: string; value: string; tolerance: string | null };
  allowed_operator_ids: string[];
  operator_precondition_notes: Record<string, string>;
  counterfactual_transforms: Array<{ type: string; description: string; answer_mapping: string }>;
  leakage_flags: {
    used_original_distractors: boolean;
    used_human_response_dist: boolean;
    used_seed_candidates: boolean;
    original_options_removed: boolean;
  };
  quality_control: {
    manual_checked: boolean;
    answer_verified: boolean;
    trace_verified: boolean;
    operator_applicability_checked: boolean;
    counterfactual_ready: boolean;
    notes: string;
  };
}

interface Props {
  item: MechanismItem;
  uiLang: UiLanguage;
  aiBusy: boolean;
  onChange: (item: MechanismItem) => void;
  onTranslateSourceMetadata: () => Promise<void>;
}

const ANSWER_TYPES = ["numeric", "formula", "unit_quantity", "vector", "finite_set", "conceptual_binary"];
const MODIFICATION_LEVELS = ["original_clean", "numeric_perturbation", "paraphrased", "structure_preserved", "manual_rewrite"];
const CURRICULUM_LEVELS = ["elementary", "middle_school", "high_school", "undergraduate_intro", "advanced"];
const BUILT_IN_OPERATORS = [
  "ALG_SIGN_MOVE",
  "ALG_DISTRIBUTIVE_DROP",
  "ALG_ILLEGAL_CANCEL",
  "ALG_SQRT_SIGN_DROP",
  "CALC_CHAIN_RULE_DROP",
  "PHY_UNIT_CONVERSION",
  "PHY_VECTOR_SIGN",
  "PHY_SCALAR_VECTOR_CONFUSION",
  "PHY_FORMULA_DOMAIN_MISUSE",
  "PHY_CELSIUS_KELVIN_CONFUSION",
];

export const FIELD_ZH: Record<string, string> = {
  item_id: "条目编号",
  item_role: "条目角色",
  source: "来源",
  source_dataset: "来源数据集",
  source_split: "来源划分",
  source_family: "来源题型/家族",
  source_record_id: "来源记录 ID",
  license_note: "许可/来源说明",
  subject: "学科",
  domain: "领域",
  curriculum_level: "课程层级",
  question_clean: "清洗后的题干",
  question: "题目",
  question_original_available: "是否保留原始题干",
  modification_level: "改写程度",
  correct_answer: "正确答案",
  distractor_answer: "干扰项答案",
  answer_type: "答案类型",
  "answer_format.type": "答案格式类型",
  "answer_format.unit": "单位",
  "answer_format.precision": "精度",
  "construct.primary": "主要考查构念",
  "construct.secondary comma-separated": "次要构念，逗号分隔",
  givens: "已知条件",
  variables: "变量",
  constraints: "约束条件",
  solution_trace: "解题步骤",
  step_id: "步骤编号",
  premise: "依据",
  operation: "操作",
  expr_before: "操作前表达式",
  expr_after: "操作后表达式",
  verifier_hint: "验证器提示",
  "valid_answer_set.type": "答案集合验证类型",
  "valid_answer_set.value": "答案集合值",
  "valid_answer_set.tolerance": "容差",
  allowed_operator_ids: "可用错误算子",
  target_error_operator_id: "目标错误算子",
  target_error_operator_ids: "目标错误算子集合",
  "operator_precondition_notes JSON-ish summary": "算子适用条件说明",
  counterfactual_transforms: "反事实变换",
  wrong_solution_trace: "错误解题步骤",
  mechanism_note: "机制说明",
  distractor_set: "干扰项集合",
  distractor_id: "干扰项编号",
  applied_operator_ids: "已应用错误算子",
  answer: "答案",
  operator_applicability: "错误算子适用性",
  negative_control_for_operator_id: "负控制对应算子",
  negative_control_note: "负控制说明",
  data_access_mode: "数据访问模式",
  leakage_audit: "泄露审计",
  used_original_distractors: "是否使用原始干扰项",
  used_human_response_dist: "是否使用人类作答分布",
  used_seed_candidates: "是否使用种子候选项",
  original_options_removed: "原始选项已移除",
  manual_checked: "人工检查",
  answer_verified: "答案已验证",
  trace_verified: "步骤已验证",
  operator_applicability_checked: "算子适用性已检查",
  counterfactual_ready: "反事实已准备",
  notes: "备注",
  symbol: "符号",
  value: "值",
  role: "角色",
  type: "类型",
  target: "目标",
  var: "变量",
  expr: "表达式",
  result: "结果",
  metadata: "元数据",
  derived_answer: "推导答案",
  error_operator_id: "错误算子 ID",
  description: "描述",
  answer_mapping: "答案映射",
  original_distractors_removed: "原始干扰项已移除",
  human_response_dist_removed: "人类作答分布已移除",
  seed_candidates_removed: "种子候选项已移除",
  forbidden_key_scan_passed: "禁用字段扫描通过",
  canary_scan_passed: "金丝雀扫描通过",
};

const REQUIRED_LABELS = new Set([
  "item_id",
  "source_dataset",
  "subject",
  "domain",
  "question_clean",
  "correct_answer",
  "answer_type",
  "construct.primary",
  "valid_answer_set.type",
  "allowed_operator_ids",
  "solution_trace",
  "counterfactual_transforms",
  "leakage_flags",
  "quality_control",
  "manual_checked",
  "answer_verified",
  "trace_verified",
  "operator_applicability_checked",
  "counterfactual_ready",
]);

const SECTION_ZH: Record<string, string> = {
  "A. Source Metadata": "来源元数据",
  "B. Subject / Domain / Curriculum": "学科 / 领域 / 课程",
  "C. Question and Answer": "题干与答案",
  "D. Answer Format": "答案格式",
  "E. Construct": "考查构念",
  "F. Givens": "已知条件",
  "G. Variables": "变量",
  "H. Constraints": "约束",
  "I. Solution Trace": "解题步骤",
  "J. Valid Answer Set": "有效答案集合",
  "K. Error Operators": "错误算子",
  "L. Counterfactual Transforms": "反事实变换",
  "M. Leakage Flags": "泄露标记",
  "N. Quality Control": "质量控制",
  "O. JSON Preview": "JSON 预览",
};

export const OPERATOR_ZH: Record<string, string> = {
  ALG_SIGN_MOVE: "移项变号错误",
  ALG_DISTRIBUTIVE_DROP: "分配律漏乘",
  ALG_ILLEGAL_CANCEL: "非法约分",
  ALG_SQRT_SIGN_DROP: "平方根正负号遗漏",
  CALC_CHAIN_RULE_DROP: "链式法则遗漏",
  PHY_UNIT_CONVERSION: "单位换算错误",
  PHY_VECTOR_SIGN: "向量方向符号错误",
  PHY_SCALAR_VECTOR_CONFUSION: "标量/向量混淆",
  PHY_FORMULA_DOMAIN_MISUSE: "公式适用条件误用",
  PHY_CELSIUS_KELVIN_CONFUSION: "摄氏/开尔文混淆",
};

export function defaultItem(): MechanismItem {
  return {
    item_id: "",
    source_metadata_zh: {
      item_id: "",
      source_dataset: "",
      source_split: "",
      source_family: "",
      source_record_id: "",
      license_note: "",
    },
    source_dataset: "MATH",
    source_split: "train",
    source_family: "competition_math",
    source_record_id: "",
    license_note: "for research use; original options absent",
    subject: "math",
    domain: "",
    curriculum_level: "high_school",
    question_clean: "",
    question_original_available: false,
    modification_level: "original_clean",
    correct_answer: "",
    answer_type: "numeric",
    answer_format: { type: "integer", unit: null, precision: null },
    construct: { primary: "", secondary: [] },
    givens: [{ symbol: "", value: "" }],
    variables: [{ symbol: "", role: "unknown", domain: "real" }],
    constraints: [{ type: "domain", target: "", value: "" }],
    solution_trace: [
      { step_id: 1, premise: "", operation: "", expr_before: null, expr_after: "", verifier_hint: "" },
      { step_id: 2, premise: "", operation: "", expr_before: "", expr_after: "", verifier_hint: "" },
      { step_id: 3, premise: "", operation: "", expr_before: "", expr_after: "", verifier_hint: "" },
    ],
    valid_answer_set: { type: "sympy_equiv", value: "", tolerance: null },
    allowed_operator_ids: ["ALG_SIGN_MOVE", "ALG_DISTRIBUTIVE_DROP", "ALG_ILLEGAL_CANCEL"],
    operator_precondition_notes: {},
    counterfactual_transforms: [
      { type: "variable_renaming", description: "", answer_mapping: "identity" },
      { type: "numeric_perturbation", description: "", answer_mapping: "recompute" },
      { type: "paraphrase", description: "", answer_mapping: "identity" },
    ],
    leakage_flags: {
      used_original_distractors: false,
      used_human_response_dist: false,
      used_seed_candidates: false,
      original_options_removed: true,
    },
    quality_control: {
      manual_checked: false,
      answer_verified: false,
      trace_verified: false,
      operator_applicability_checked: false,
      counterfactual_ready: false,
      notes: "",
    },
  };
}

export default function OutputItemEditor({ item, uiLang, aiBusy, onChange, onTranslateSourceMetadata }: Props) {
  const [customOperator, setCustomOperator] = useState("");

  function patch(patchValue: Partial<MechanismItem>) {
    onChange({ ...item, ...patchValue });
  }

  function updateArray<T>(key: keyof MechanismItem, index: number, value: T) {
    const current = [...((item[key] as T[]) ?? [])];
    current[index] = value;
    patch({ [key]: current } as Partial<MechanismItem>);
  }

  function addArrayItem<T>(key: keyof MechanismItem, value: T) {
    const current = [...((item[key] as T[]) ?? []), value];
    patch({ [key]: current } as Partial<MechanismItem>);
  }

  function removeArrayItem<T>(key: keyof MechanismItem, index: number) {
    const current = [...((item[key] as T[]) ?? [])];
    current.splice(index, 1);
    patch({ [key]: current } as Partial<MechanismItem>);
  }

  function toggleOperator(operatorId: string) {
    const selected = item.allowed_operator_ids.includes(operatorId);
    patch({
      allowed_operator_ids: selected
        ? item.allowed_operator_ids.filter((operator) => operator !== operatorId)
        : [...item.allowed_operator_ids, operatorId],
    });
  }

  function addCustomOperator() {
    const next = customOperator.trim();
    if (!next || item.allowed_operator_ids.includes(next)) return;
    patch({ allowed_operator_ids: [...item.allowed_operator_ids, next] });
    setCustomOperator("");
  }

  function removeOperator(operatorId: string) {
    patch({ allowed_operator_ids: item.allowed_operator_ids.filter((operator) => operator !== operatorId) });
  }

  function updateSourceMetadataZh(field: string, value: string) {
    patch({
      source_metadata_zh: {
        ...(item.source_metadata_zh ?? {}),
        [field]: value,
      },
    });
  }

  return (
    <section className="output-editor">
      <Section title="A. Source Metadata" defaultOpen>
        <div className="section-toolbar">
          <button onClick={onTranslateSourceMetadata} disabled={aiBusy}>
            {buttonLabel(uiLang, "aiTranslateEnglish")}
          </button>
        </div>
        <div className="bilingual-header">
          <span>中文（可填写）</span>
          <span>English output</span>
        </div>
        <BilingualText
          label="item_id"
          zhValue={item.source_metadata_zh?.item_id ?? ""}
          enValue={item.item_id}
          onZhChange={(value) => updateSourceMetadataZh("item_id", value)}
          onEnChange={(value) => patch({ item_id: value })}
        />
        <BilingualText
          label="source_dataset"
          zhValue={item.source_metadata_zh?.source_dataset ?? ""}
          enValue={item.source_dataset}
          onZhChange={(value) => updateSourceMetadataZh("source_dataset", value)}
          onEnChange={(value) => patch({ source_dataset: value })}
        />
        <BilingualText
          label="source_split"
          zhValue={item.source_metadata_zh?.source_split ?? ""}
          enValue={item.source_split}
          onZhChange={(value) => updateSourceMetadataZh("source_split", value)}
          onEnChange={(value) => patch({ source_split: value })}
        />
        <BilingualText
          label="source_family"
          zhValue={item.source_metadata_zh?.source_family ?? ""}
          enValue={item.source_family}
          onZhChange={(value) => updateSourceMetadataZh("source_family", value)}
          onEnChange={(value) => patch({ source_family: value })}
        />
        <BilingualText
          label="source_record_id"
          zhValue={item.source_metadata_zh?.source_record_id ?? ""}
          enValue={item.source_record_id}
          onZhChange={(value) => updateSourceMetadataZh("source_record_id", value)}
          onEnChange={(value) => patch({ source_record_id: value })}
        />
        <BilingualText
          label="license_note"
          zhValue={item.source_metadata_zh?.license_note ?? ""}
          enValue={item.license_note}
          onZhChange={(value) => updateSourceMetadataZh("license_note", value)}
          onEnChange={(value) => patch({ license_note: value })}
        />
      </Section>

      <Section title="B. Subject / Domain / Curriculum">
        <Select label="subject" value={item.subject} options={["math", "physics"]} onChange={(value) => patch({ subject: value })} />
        <Text label="domain" value={item.domain} onChange={(value) => patch({ domain: value })} />
        <Select
          label="curriculum_level"
          value={item.curriculum_level}
          options={CURRICULUM_LEVELS}
          onChange={(value) => patch({ curriculum_level: value })}
        />
      </Section>

      <Section title="C. Question and Answer" defaultOpen>
        <TextArea label="question_clean" value={item.question_clean} onChange={(value) => patch({ question_clean: value })} />
        <Check
          label="question_original_available"
          checked={item.question_original_available}
          onChange={(checked) => patch({ question_original_available: checked })}
        />
        <Select
          label="modification_level"
          value={item.modification_level}
          options={MODIFICATION_LEVELS}
          onChange={(value) => patch({ modification_level: value })}
        />
        <Text label="correct_answer" value={item.correct_answer} onChange={(value) => patch({ correct_answer: value })} />
        <Select label="answer_type" value={item.answer_type} options={ANSWER_TYPES} onChange={(value) => patch({ answer_type: value })} />
      </Section>

      <Section title="D. Answer Format">
        <Text
          label="answer_format.type"
          value={item.answer_format.type}
          onChange={(value) => patch({ answer_format: { ...item.answer_format, type: value } })}
        />
        <Text
          label="answer_format.unit"
          value={item.answer_format.unit ?? ""}
          onChange={(value) => patch({ answer_format: { ...item.answer_format, unit: value || null } })}
        />
        <Text
          label="answer_format.precision"
          value={item.answer_format.precision ?? ""}
          onChange={(value) => patch({ answer_format: { ...item.answer_format, precision: value || null } })}
        />
      </Section>

      <Section title="E. Construct">
        <Text label="construct.primary" value={item.construct.primary} onChange={(value) => patch({ construct: { ...item.construct, primary: value } })} />
        <Text
          label="construct.secondary comma-separated"
          value={item.construct.secondary.join(", ")}
          onChange={(value) =>
            patch({
              construct: {
                ...item.construct,
                secondary: value.split(",").map((entry) => entry.trim()).filter(Boolean),
              },
            })
          }
        />
      </Section>

      <Section title="F. Givens">
        {item.givens.map((given, index) => (
          <div key={index} className="row-editor two">
            <label className="field-label compact-field">
              <KeyLabel label="symbol" />
              <input value={given.symbol} onChange={(event) => updateArray("givens", index, { ...given, symbol: event.target.value })} />
            </label>
            <label className="field-label compact-field">
              <KeyLabel label="value" />
              <input value={given.value} onChange={(event) => updateArray("givens", index, { ...given, value: event.target.value })} />
            </label>
            <button onClick={() => removeArrayItem("givens", index)}>{buttonLabel(uiLang, "remove")}</button>
          </div>
        ))}
        <button onClick={() => addArrayItem("givens", { symbol: "", value: "" })}>{buttonLabel(uiLang, "addGiven")}</button>
      </Section>

      <Section title="G. Variables">
        {item.variables.map((variable, index) => (
          <div key={index} className="row-editor three">
            <label className="field-label compact-field">
              <KeyLabel label="symbol" />
              <input value={variable.symbol} onChange={(event) => updateArray("variables", index, { ...variable, symbol: event.target.value })} />
            </label>
            <label className="field-label compact-field">
              <KeyLabel label="role" />
              <input value={variable.role} onChange={(event) => updateArray("variables", index, { ...variable, role: event.target.value })} />
            </label>
            <label className="field-label compact-field">
              <KeyLabel label="domain" />
              <input value={variable.domain} onChange={(event) => updateArray("variables", index, { ...variable, domain: event.target.value })} />
            </label>
            <button onClick={() => removeArrayItem("variables", index)}>{buttonLabel(uiLang, "remove")}</button>
          </div>
        ))}
        <button onClick={() => addArrayItem("variables", { symbol: "", role: "", domain: "" })}>{buttonLabel(uiLang, "addVariable")}</button>
      </Section>

      <Section title="H. Constraints">
        {item.constraints.map((constraint, index) => (
          <div key={index} className="row-editor three">
            <label className="field-label compact-field">
              <KeyLabel label="type" />
              <input value={constraint.type} onChange={(event) => updateArray("constraints", index, { ...constraint, type: event.target.value })} />
            </label>
            <label className="field-label compact-field">
              <KeyLabel label="target" />
              <input value={constraint.target} onChange={(event) => updateArray("constraints", index, { ...constraint, target: event.target.value })} />
            </label>
            <label className="field-label compact-field">
              <KeyLabel label="value" />
              <input value={constraint.value} onChange={(event) => updateArray("constraints", index, { ...constraint, value: event.target.value })} />
            </label>
            <button onClick={() => removeArrayItem("constraints", index)}>{buttonLabel(uiLang, "remove")}</button>
          </div>
        ))}
        <button onClick={() => addArrayItem("constraints", { type: "", target: "", value: "" })}>{buttonLabel(uiLang, "addConstraint")}</button>
      </Section>

      <Section title="I. Solution Trace" defaultOpen requiredField="solution_trace">
        {item.solution_trace.map((step, index) => (
          <div key={index} className="trace-step">
            <div className="trace-title">Step {step.step_id}</div>
            <Text label="premise" value={step.premise} onChange={(value) => updateArray("solution_trace", index, { ...step, premise: value })} />
            <Text label="operation" value={step.operation} onChange={(value) => updateArray("solution_trace", index, { ...step, operation: value })} />
            <Text label="expr_before" value={step.expr_before ?? ""} onChange={(value) => updateArray("solution_trace", index, { ...step, expr_before: value || null })} />
            <Text label="expr_after" value={step.expr_after ?? ""} onChange={(value) => updateArray("solution_trace", index, { ...step, expr_after: value || null })} />
            <Text label="verifier_hint" value={step.verifier_hint ?? ""} onChange={(value) => updateArray("solution_trace", index, { ...step, verifier_hint: value || null })} />
            <button onClick={() => removeArrayItem("solution_trace", index)}>{buttonLabel(uiLang, "removeStep")}</button>
          </div>
        ))}
        <button
          onClick={() =>
            addArrayItem("solution_trace", {
              step_id: item.solution_trace.length + 1,
              premise: "",
              operation: "",
              expr_before: "",
              expr_after: "",
              verifier_hint: "",
            })
          }
        >
          {buttonLabel(uiLang, "addStep")}
        </button>
      </Section>

      <Section title="J. Valid Answer Set">
        <Text
          label="valid_answer_set.type"
          value={item.valid_answer_set.type}
          onChange={(value) => patch({ valid_answer_set: { ...item.valid_answer_set, type: value } })}
        />
        <Text
          label="valid_answer_set.value"
          value={item.valid_answer_set.value}
          onChange={(value) => patch({ valid_answer_set: { ...item.valid_answer_set, value } })}
        />
        <Text
          label="valid_answer_set.tolerance"
          value={item.valid_answer_set.tolerance ?? ""}
          onChange={(value) => patch({ valid_answer_set: { ...item.valid_answer_set, tolerance: value || null } })}
        />
      </Section>

      <Section title="K. Error Operators" defaultOpen requiredField="allowed_operator_ids">
        <KeyLabel label="allowed_operator_ids" />
        <div className="chips">
          {BUILT_IN_OPERATORS.map((operator) => (
            <button
              key={operator}
              className={`chip ${item.allowed_operator_ids.includes(operator) ? "selected" : ""}`}
              onClick={() => toggleOperator(operator)}
            >
              <span>{operator}</span>
              <small>{OPERATOR_ZH[operator]}</small>
            </button>
          ))}
          {item.allowed_operator_ids
            .filter((operator) => !BUILT_IN_OPERATORS.includes(operator))
            .map((operator) => (
              <button key={operator} className="chip selected" onClick={() => removeOperator(operator)}>
                <span>{operator}</span>
                <small>自定义错误算子，点击移除</small>
              </button>
            ))}
        </div>
        <div className="inline-add">
          <input value={customOperator} onChange={(event) => setCustomOperator(event.target.value)} placeholder="CUSTOM_OPERATOR_ID" />
          <button onClick={addCustomOperator}>{buttonLabel(uiLang, "add")}</button>
        </div>
        <TextArea
          label="operator_precondition_notes JSON-ish summary"
          value={Object.entries(item.operator_precondition_notes).map(([key, value]) => `${key}: ${value}`).join("\n")}
          onChange={(value) => {
            const notes: Record<string, string> = {};
            value.split("\n").forEach((line) => {
              const [key, ...rest] = line.split(":");
              if (key?.trim()) notes[key.trim()] = rest.join(":").trim();
            });
            patch({ operator_precondition_notes: notes });
          }}
        />
      </Section>

      <Section title="L. Counterfactual Transforms" requiredField="counterfactual_transforms">
        {item.counterfactual_transforms.map((transform, index) => (
          <div key={index} className="row-editor three">
            <label className="field-label compact-field">
              <KeyLabel label="type" />
              <input value={transform.type} onChange={(event) => updateArray("counterfactual_transforms", index, { ...transform, type: event.target.value })} />
            </label>
            <label className="field-label compact-field">
              <KeyLabel label="description" />
              <input value={transform.description} onChange={(event) => updateArray("counterfactual_transforms", index, { ...transform, description: event.target.value })} />
            </label>
            <label className="field-label compact-field">
              <KeyLabel label="answer_mapping" />
              <input value={transform.answer_mapping} onChange={(event) => updateArray("counterfactual_transforms", index, { ...transform, answer_mapping: event.target.value })} />
            </label>
            <button onClick={() => removeArrayItem("counterfactual_transforms", index)}>{buttonLabel(uiLang, "remove")}</button>
          </div>
        ))}
        <button onClick={() => addArrayItem("counterfactual_transforms", { type: "", description: "", answer_mapping: "" })}>{buttonLabel(uiLang, "addTransform")}</button>
      </Section>

      <Section title="M. Leakage Flags" defaultOpen requiredField="leakage_flags">
        <Check label="used_original_distractors" checked={item.leakage_flags.used_original_distractors} onChange={(checked) => patch({ leakage_flags: { ...item.leakage_flags, used_original_distractors: checked } })} />
        <Check label="used_human_response_dist" checked={item.leakage_flags.used_human_response_dist} onChange={(checked) => patch({ leakage_flags: { ...item.leakage_flags, used_human_response_dist: checked } })} />
        <Check label="used_seed_candidates" checked={item.leakage_flags.used_seed_candidates} onChange={(checked) => patch({ leakage_flags: { ...item.leakage_flags, used_seed_candidates: checked } })} />
        <Check label="original_options_removed" checked={item.leakage_flags.original_options_removed} onChange={(checked) => patch({ leakage_flags: { ...item.leakage_flags, original_options_removed: checked } })} />
      </Section>

      <Section title="N. Quality Control" defaultOpen requiredField="quality_control">
        <Check label="manual_checked" checked={item.quality_control.manual_checked} onChange={(checked) => patch({ quality_control: { ...item.quality_control, manual_checked: checked } })} />
        <Check label="answer_verified" checked={item.quality_control.answer_verified} onChange={(checked) => patch({ quality_control: { ...item.quality_control, answer_verified: checked } })} />
        <Check label="trace_verified" checked={item.quality_control.trace_verified} onChange={(checked) => patch({ quality_control: { ...item.quality_control, trace_verified: checked } })} />
        <Check label="operator_applicability_checked" checked={item.quality_control.operator_applicability_checked} onChange={(checked) => patch({ quality_control: { ...item.quality_control, operator_applicability_checked: checked } })} />
        <Check label="counterfactual_ready" checked={item.quality_control.counterfactual_ready} onChange={(checked) => patch({ quality_control: { ...item.quality_control, counterfactual_ready: checked } })} />
        <TextArea label="notes" value={item.quality_control.notes} onChange={(value) => patch({ quality_control: { ...item.quality_control, notes: value } })} />
      </Section>

      <Section title="O. JSON Preview">
        <pre className="json-preview">{JSON.stringify(outputOnlyItem(item), null, 2)}</pre>
      </Section>
    </section>
  );
}

function outputOnlyItem(item: MechanismItem): Omit<MechanismItem, "source_metadata_zh"> {
  const { source_metadata_zh: _sourceMetadataZh, ...outputItem } = item;
  return outputItem;
}

function Section({
  title,
  defaultOpen = false,
  requiredField,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  requiredField?: string;
  children: ReactNode;
}) {
  return (
    <details className="editor-section" open={defaultOpen}>
      <summary>
        <span>
          {title}
          {requiredField && REQUIRED_LABELS.has(requiredField) && <b className="required-star">*</b>}
        </span>
        <small>{SECTION_ZH[title]}</small>
      </summary>
      <div className="section-body">{children}</div>
    </details>
  );
}

function Text({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field-label">
      <KeyLabel label={label} />
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function BilingualText({
  label,
  zhValue,
  enValue,
  onZhChange,
  onEnChange,
}: {
  label: string;
  zhValue: string;
  enValue: string;
  onZhChange: (value: string) => void;
  onEnChange: (value: string) => void;
}) {
  return (
    <div className="bilingual-row">
      <label className="field-label">
        <KeyLabel label={label} />
        <input value={zhValue} onChange={(event) => onZhChange(event.target.value)} placeholder="中文输入" />
      </label>
      <label className="field-label">
        <KeyLabel label={label} />
        <input value={enValue} onChange={(event) => onEnChange(event.target.value)} placeholder="English output" />
      </label>
    </div>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field-label">
      <KeyLabel label={label} />
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={4} />
    </label>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="field-label">
      <KeyLabel label={label} />
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="checkbox-line">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <KeyLabel label={label} inline />
    </label>
  );
}

function KeyLabel({ label, inline = false }: { label: string; inline?: boolean }) {
  return (
    <span className={inline ? "key-label inline" : "key-label"}>
      <span>
        {label}
        {REQUIRED_LABELS.has(label) && <b className="required-star">*</b>}
      </span>
      <small>{FIELD_ZH[label] ?? "自定义字段"}</small>
    </span>
  );
}
