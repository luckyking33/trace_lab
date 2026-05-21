import { buttonLabel, DatasetRecord, DatasetSummary, UiLanguage } from "../api";
import NavigationBar from "./NavigationBar";
import JsonTreeView from "./JsonTreeView";
import { FIELD_ZH, MechanismItem, OPERATOR_ZH } from "./OutputItemEditor";
import LatexText from "./LatexText";

interface Props {
  uiLang: UiLanguage;
  dataset: DatasetSummary | null;
  record: DatasetRecord | null;
  index: number;
  translations: Record<string, string>;
  aiBusy: boolean;
  title?: string;
  emptyMessage?: string;
  showOutputActions?: boolean;
  onNavigate: (index: number) => Promise<void>;
  onCopyToOutput?: (field: keyof MechanismItem, value: unknown) => void;
  onTranslateField: (fieldName: string, value: string) => Promise<void>;
}

type JsonObject = Record<string, unknown>;

const SENSITIVE_FIELDS = [
  "choices",
  "options",
  "distractors",
  "human_response_dist",
  "student_choice",
  "choice_logs",
  "seed_candidates",
  "item_stats",
  "original_options",
  "option_frequency",
];

export default function RawRecordViewer({
  uiLang,
  dataset,
  record,
  index,
  translations,
  aiBusy,
  title = "Raw Input Record",
  emptyMessage = "Load a dataset to inspect records.",
  showOutputActions = true,
  onNavigate,
  onCopyToOutput,
  onTranslateField,
}: Props) {
  const entries = Object.entries(record?.record ?? {});
  return (
    <section className="raw-pane">
      <div className="pane-header">
        <h2>{title}</h2>
        {dataset && <span>{dataset.num_rows.toLocaleString()} rows</span>}
      </div>
      {!dataset && <p className="muted">{emptyMessage}</p>}
      {record?.leakage_warnings.length ? (
        <div className="leakage-banner">Leakage-sensitive raw fields detected: {record.leakage_warnings.join(", ")}</div>
      ) : null}
      <div className="raw-record-list">
        {entries.map(([field, value]) => {
          const sensitive = isSensitive(field);
          const longText = typeof value === "string" && value.length > 320;
          const openByDefault = !sensitive && (!longText || isPrimaryTextField(field) || isMechanismKeyField(field));
          const translation = record ? translations[translationKey(record.dataset_id, record.index, field)] : "";
          return (
            <details key={field} className={`field-card ${sensitive ? "field-warning" : ""}`} open={openByDefault}>
              <summary>
                <span className="field-name">
                  <span>{field}</span>
                  <small>{FIELD_ZH[field] ?? "自定义字段"}</small>
                </span>
                <small>{typeLabel(value)}</small>
              </summary>
              <div className="field-value">
                <FieldValue field={field} value={value} translation={translation} />
              </div>
              <div className="field-actions">
                <button onClick={() => navigator.clipboard.writeText(String(value ?? ""))}>{buttonLabel(uiLang, "copyValue")}</button>
                {!sensitive && (
                  <>
                    {showOutputActions && onCopyToOutput && (
                      <>
                        <button onClick={() => onCopyToOutput("question_clean", value)}>{buttonLabel(uiLang, "copyQuestion")}</button>
                        <button onClick={() => onCopyToOutput("source_record_id", `${dataset?.dataset_id ?? "dataset"}:${index}:${field}`)}>
                          {buttonLabel(uiLang, "copyRecordRef")}
                        </button>
                      </>
                    )}
                    {typeof value === "string" && isPrimaryTextField(field) && (
                      <button onClick={() => onTranslateField(field, value)} disabled={aiBusy}>
                        {buttonLabel(uiLang, "translateProblem")}
                      </button>
                    )}
                  </>
                )}
                {sensitive && <span className="blocked-copy">Copy to output disabled</span>}
              </div>
            </details>
          );
        })}
      </div>
      {dataset && <NavigationBar uiLang={uiLang} index={index} total={dataset.num_rows} onNavigate={onNavigate} />}
    </section>
  );
}

function FieldValue({ field, value, translation }: { field: string; value: unknown; translation?: string }) {
  if (isOperatorField(field) && isOperatorPayload(value)) {
    const operators = Array.isArray(value) ? value.map(String) : [String(value)];
    return <OperatorChips operators={operators} />;
  }

  if (typeof value === "string") {
    return (
      <>
        <LatexText text={value} />
        {translation && (
          <div className="translation-panel">
            <strong>中文翻译</strong>
            <LatexText text={translation} />
          </div>
        )}
      </>
    );
  }

  if (isAnswerField(field) && isObject(value)) {
    return <AnswerCard value={value} />;
  }

  if ((field === "solution_trace" || field === "wrong_solution_trace") && Array.isArray(value)) {
    return <TraceTimeline steps={value} variant={field === "wrong_solution_trace" ? "wrong" : "correct"} />;
  }

  if (field === "givens" && Array.isArray(value)) {
    return <KeyValueTable rows={value} preferredKeys={["symbol", "value"]} />;
  }

  if (field === "constraints" && Array.isArray(value)) {
    return <KeyValueTable rows={value} preferredKeys={["var", "target", "domain", "type", "value"]} />;
  }

  if (field === "distractor_set" && Array.isArray(value)) {
    return <DistractorSet distractors={value} />;
  }

  if (field === "counterfactual_transforms" && Array.isArray(value)) {
    return <TransformChips transforms={value} />;
  }

  if ((field === "leakage_flags" || field === "leakage_audit" || field === "operator_applicability") && isObject(value)) {
    return <BooleanGrid value={value} />;
  }

  if (typeof value === "object" && value !== null) {
    return <JsonTreeView value={value} />;
  }

  return <pre>{String(value ?? "")}</pre>;
}

function DistractorSet({ distractors }: { distractors: unknown[] }) {
  if (distractors.length === 0) {
    return <p className="muted">No distractors for this item.</p>;
  }

  return (
    <div className="distractor-set">
      {distractors.map((rawDistractor, index) => {
        const distractor = isObject(rawDistractor) ? rawDistractor : { value: rawDistractor };
        const id = String(distractor.distractor_id ?? `D${index + 1}`);
        const appliedOperators = Array.isArray(distractor.applied_operator_ids)
          ? distractor.applied_operator_ids.map(String)
          : [];
        return (
          <article key={id} className="distractor-card">
            <div className="distractor-header">
              <div>
                <strong>{id}</strong>
                <small>{FIELD_ZH.distractor_id}</small>
              </div>
              <OperatorChips operators={appliedOperators} />
            </div>

            {isObject(distractor.answer) && (
              <div>
                <div className="subsection-title">{FIELD_ZH.answer}</div>
                <AnswerCard value={distractor.answer} />
              </div>
            )}

            {Array.isArray(distractor.wrong_solution_trace) && (
              <div>
                <div className="subsection-title">{FIELD_ZH.wrong_solution_trace}</div>
                <TraceTimeline steps={distractor.wrong_solution_trace} variant="wrong" />
              </div>
            )}

            {typeof distractor.mechanism_note === "string" && (
              <div>
                <div className="subsection-title">{FIELD_ZH.mechanism_note}</div>
                <LatexText text={distractor.mechanism_note} />
              </div>
            )}

            {Object.keys(distractor).some(
              (key) => !["distractor_id", "applied_operator_ids", "answer", "wrong_solution_trace", "mechanism_note"].includes(key),
            ) && <JsonTreeView value={distractor} />}
          </article>
        );
      })}
    </div>
  );
}

function AnswerCard({ value }: { value: JsonObject }) {
  return (
    <div className="answer-card">
      {Object.entries(value).map(([key, entry]) => (
        <div key={key}>
          <span>{key}</span>
          <small>{FIELD_ZH[key] ?? "自定义字段"}</small>
          <strong>{String(entry ?? "")}</strong>
        </div>
      ))}
    </div>
  );
}

function TraceTimeline({ steps, variant }: { steps: unknown[]; variant: "correct" | "wrong" }) {
  return (
    <div className={`trace-timeline ${variant}`}>
      {steps.map((rawStep, index) => {
        const step = isObject(rawStep) ? rawStep : { value: rawStep };
        const stepId = step.step_id ?? index + 1;
        const metadata = isObject(step.metadata) ? step.metadata : null;
        return (
          <div key={index} className="trace-row">
            <div className="trace-badge">{String(stepId)}</div>
            <div className="trace-content">
              {step.expr !== undefined && (
                <div className="trace-expr">
                  <LatexText text={String(step.expr)} />
                </div>
              )}
              {step.operation !== undefined && (
                <div className="trace-operation">
                  <span>{FIELD_ZH.operation}</span>
                  <strong>{String(step.operation)}</strong>
                </div>
              )}
              {step.result !== undefined && step.result !== null && (
                <div className="trace-result">
                  <span>{FIELD_ZH.result}</span>
                  <strong>{String(step.result)}</strong>
                </div>
              )}
              {metadata && Object.keys(metadata).length > 0 && (
                <div className="trace-metadata">
                  {Object.entries(metadata).map(([key, entry]) => (
                    <span key={key}>
                      {FIELD_ZH[key] ?? key}: {String(entry ?? "")}
                    </span>
                  ))}
                </div>
              )}
              {step.expr === undefined && <JsonTreeView value={step} />}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function KeyValueTable({ rows, preferredKeys }: { rows: unknown[]; preferredKeys: string[] }) {
  return (
    <div className="kv-table">
      {rows.map((row, index) => {
        const obj = isObject(row) ? row : { value: row };
        const keys = [...preferredKeys.filter((key) => key in obj), ...Object.keys(obj).filter((key) => !preferredKeys.includes(key))];
        return (
          <div key={index} className="kv-row">
            {keys.map((key) => (
              <div key={key}>
                <span>{key}</span>
                <small>{FIELD_ZH[key] ?? "自定义字段"}</small>
                <strong>{String(obj[key] ?? "")}</strong>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function OperatorChips({ operators }: { operators: string[] }) {
  if (operators.length === 0) {
    return <p className="muted">No operators.</p>;
  }

  return (
    <div className="chips">
      {operators.map((operator) => (
        <span key={operator} className="readonly-chip operator-chip">
          <strong>{operator}</strong>
          <small>{OPERATOR_ZH[operator] ?? "自定义错误算子"}</small>
        </span>
      ))}
    </div>
  );
}

function TransformChips({ transforms }: { transforms: unknown[] }) {
  return (
    <div className="chips">
      {transforms.map((transform, index) => (
        <span key={`${String(transform)}-${index}`} className="readonly-chip">
          {String(transform)}
        </span>
      ))}
    </div>
  );
}

function BooleanGrid({ value }: { value: JsonObject }) {
  return (
    <div className="boolean-grid">
      {Object.entries(value).map(([key, entry]) => (
        <div key={key} className={entry === true ? "bool-true" : "bool-false"}>
          <span>{key}</span>
          <small>{FIELD_ZH[key] ?? OPERATOR_ZH[key] ?? "自定义字段"}</small>
          <strong>{String(entry)}</strong>
        </div>
      ))}
    </div>
  );
}

function isSensitive(field: string): boolean {
  const key = field.toLowerCase();
  return SENSITIVE_FIELDS.some((candidate) => key.includes(candidate));
}

function typeLabel(value: unknown): string {
  if (Array.isArray(value)) return `array[${value.length}]`;
  if (value === null) return "null";
  return typeof value;
}

function isPrimaryTextField(field: string): boolean {
  const key = field.toLowerCase();
  return ["problem", "question", "prompt", "stem"].some((candidate) => key.includes(candidate));
}

function isMechanismKeyField(field: string): boolean {
  return [
    "correct_answer",
    "distractor_answer",
    "solution_trace",
    "wrong_solution_trace",
    "allowed_operator_ids",
    "target_error_operator_id",
    "target_error_operator_ids",
    "negative_control_for_operator_id",
    "operator_applicability",
    "distractor_set",
    "leakage_audit",
    "mechanism_note",
    "negative_control_note",
  ].includes(field);
}

function isAnswerField(field: string): boolean {
  return field === "correct_answer" || field === "distractor_answer";
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOperatorPayload(value: unknown): boolean {
  return typeof value === "string" || (Array.isArray(value) && value.every((entry) => typeof entry === "string"));
}

function isOperatorField(field: string): boolean {
  return [
    "allowed_operator_ids",
    "target_error_operator_id",
    "target_error_operator_ids",
    "negative_control_for_operator_id",
    "applied_operator_ids",
  ].includes(field);
}

function translationKey(datasetId: string, recordIndex: number, fieldName: string): string {
  return `${datasetId}:${recordIndex}:${fieldName}`;
}
