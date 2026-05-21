import { useState } from "react";
import { buttonLabel, UiLanguage, Workspace } from "../api";

interface Props {
  uiLang: UiLanguage;
  workspace: Workspace | null;
  activeDatasetId: string | null;
  onLoadDataset: (path: string) => Promise<void>;
  onSelectDataset: (datasetId: string) => Promise<void>;
  onRemoveDataset: (datasetId: string) => Promise<void>;
}

export default function DatasetSidebar({
  uiLang,
  workspace,
  activeDatasetId,
  onLoadDataset,
  onSelectDataset,
  onRemoveDataset,
}: Props) {
  const [path, setPath] = useState("data/competition_math/train/data-00000-of-00001.arrow");

  async function handleLoad() {
    if (!path.trim()) return;
    await onLoadDataset(path.trim());
  }

  return (
    <aside className="dataset-sidebar">
      <div className="pane-header">
        <h2>Datasets</h2>
        <button onClick={handleLoad} disabled={!workspace}>
          {buttonLabel(uiLang, "loadDataset")}
        </button>
      </div>
      <textarea
        value={path}
        onChange={(event) => setPath(event.target.value)}
        rows={3}
        placeholder="data/competition_math/train/data-00000-of-00001.arrow"
      />
      <div className="dataset-list">
        {!workspace && <p className="muted">Create or select a workspace first.</p>}
        {workspace?.loaded_input_datasets.map((dataset) => (
          <div
            key={dataset.dataset_id}
            className={`dataset-card ${dataset.dataset_id === activeDatasetId ? "active" : ""}`}
          >
            <button className="dataset-title" onClick={() => onSelectDataset(dataset.dataset_id)}>
              {dataset.path}
            </button>
            <dl>
              <dt>ID</dt>
              <dd>{dataset.dataset_id}</dd>
              <dt>Format</dt>
              <dd>{dataset.format}</dd>
              <dt>Rows</dt>
              <dd>{dataset.num_rows.toLocaleString()}</dd>
              <dt>Fields</dt>
              <dd>{dataset.fields.join(", ")}</dd>
            </dl>
            <button className="danger subtle" onClick={() => onRemoveDataset(dataset.dataset_id)}>
              {buttonLabel(uiLang, "remove")}
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
