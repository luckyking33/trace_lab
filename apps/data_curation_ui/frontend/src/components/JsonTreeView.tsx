import { FIELD_ZH } from "./OutputItemEditor";

interface Props {
  value: unknown;
  depth?: number;
}

export default function JsonTreeView({ value, depth = 0 }: Props) {
  if (value === null || typeof value !== "object") {
    return <span className="json-scalar">{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <div className="json-tree" style={{ paddingLeft: depth ? 12 : 0 }}>
        {value.map((entry, index) => (
          <details key={index} open={depth < 1}>
            <summary>[{index}]</summary>
            <JsonTreeView value={entry} depth={depth + 1} />
          </details>
        ))}
      </div>
    );
  }
  const entries = Object.entries(value as Record<string, unknown>);
  return (
    <div className="json-tree" style={{ paddingLeft: depth ? 12 : 0 }}>
      {entries.map(([key, entry]) => (
        <details key={key} open={depth < 1}>
          <summary>
            <span>{key}</span>
            <small>{FIELD_ZH[key] ?? "自定义字段"}</small>
          </summary>
          <JsonTreeView value={entry} depth={depth + 1} />
        </details>
      ))}
    </div>
  );
}
