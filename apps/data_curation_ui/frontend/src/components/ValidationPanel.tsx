import { ValidationResponse } from "../api";

interface Props {
  validation: ValidationResponse | null;
  rawWarnings: string[];
}

export default function ValidationPanel({ validation, rawWarnings }: Props) {
  const errors = validation?.errors ?? [];
  const warnings = [...(validation?.warnings ?? []), ...rawWarnings.map((warning) => ({
    severity: "warning" as const,
    path: "raw_record",
    message: warning,
  }))];
  return (
    <section className="validation-panel">
      <div className="pane-header compact">
        <h2>Validation</h2>
        <span className={validation?.valid ? "status-ok" : "status-bad"}>
          {validation?.valid ? "ready" : `${errors.length} errors`}
        </span>
      </div>
      {errors.length === 0 && warnings.length === 0 && <p className="muted">No validation messages yet.</p>}
      {errors.map((issue, index) => (
        <div key={`error-${index}`} className="validation-item error">
          <strong>{issue.path}</strong>
          <span>{issue.message}</span>
        </div>
      ))}
      {warnings.map((issue, index) => (
        <div key={`warning-${index}`} className="validation-item warning">
          <strong>{issue.path}</strong>
          <span>{issue.message}</span>
        </div>
      ))}
    </section>
  );
}

