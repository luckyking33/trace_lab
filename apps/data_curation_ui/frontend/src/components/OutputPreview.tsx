import { OutputStatus } from "../api";
import { MechanismItem } from "./OutputItemEditor";

interface Props {
  item: MechanismItem;
  outputStatus: OutputStatus | null;
}

export default function OutputPreview({ item, outputStatus }: Props) {
  return (
    <section className="output-preview">
      <div className="pane-header compact">
        <h2>Output Dataset</h2>
        <span>{outputStatus?.output_path ?? "not configured"}</span>
      </div>
      <dl className="status-grid">
        <dt>Item count</dt>
        <dd>{outputStatus?.item_count ?? 0}</dd>
        <dt>Last item_id</dt>
        <dd>{outputStatus?.last_item_id ?? "none"}</dd>
        <dt>Current item_id</dt>
        <dd>{item.item_id || "missing"}</dd>
      </dl>
    </section>
  );
}

