import { useEffect, useMemo, useState } from "react";
import { api, buttonLabel, JsonlMeta, JsonlRecord, JsonlRecordsPage, UiLanguage } from "../api";
import JsonTreeView from "./JsonTreeView";
import RawRecordViewer from "./RawRecordViewer";

interface Props {
  uiLang: UiLanguage;
  initialPath?: string;
}

const PAGE_SIZE = 20;
const DEFAULT_JSONL_PATH = "data/mechanism_invariant_operator_45.jsonl";

export default function JsonlViewerPage({ uiLang, initialPath = "" }: Props) {
  const [path, setPath] = useState(initialPath || DEFAULT_JSONL_PATH);
  const [meta, setMeta] = useState<JsonlMeta | null>(null);
  const [record, setRecord] = useState<JsonlRecord | null>(null);
  const [index, setIndex] = useState(0);
  const [page, setPage] = useState<JsonlRecordsPage | null>(null);
  const [pageOffset, setPageOffset] = useState(0);
  const [translations, setTranslations] = useState<Record<string, string>>({});
  const [aiBusy, setAiBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void loadJsonl(path);
  }, []);

  useEffect(() => {
    if (initialPath && (!path || path === DEFAULT_JSONL_PATH)) setPath(initialPath);
  }, [initialPath, path]);

  const activeDataset = useMemo(() => {
    if (!meta) return null;
    return {
      dataset_id: meta.dataset_id,
      path: meta.path,
      format: meta.format,
      num_rows: meta.num_rows,
      fields: meta.fields,
      field_types: meta.field_types,
    };
  }, [meta]);

  async function loadJsonl(nextPath = path) {
    clearNotices();
    try {
      const loadedMeta = await api.getJsonlMeta(nextPath);
      setMeta(loadedMeta);
      setPath(loadedMeta.path);
      setPageOffset(0);
      setTranslations({});
      if (loadedMeta.num_rows > 0) {
        await loadRecord(loadedMeta.path, 0);
      } else {
        setRecord(null);
        setIndex(0);
      }
      await loadPage(loadedMeta.path, 0);
      setMessage(`Loaded ${loadedMeta.num_rows} JSONL rows from ${loadedMeta.path}`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function loadRecord(nextPath: string, nextIndex: number) {
    clearNotices();
    const nextRecord = await api.getJsonlRecord(nextPath, nextIndex);
    setRecord(nextRecord);
    setIndex(nextIndex);
    await hydrateCachedTranslations(nextRecord);
  }

  async function loadPage(nextPath: string, offset: number) {
    const nextPage = await api.getJsonlRecords(nextPath, offset, PAGE_SIZE);
    setPage(nextPage);
    setPageOffset(offset);
  }

  async function navigate(nextIndex: number) {
    if (!meta) return;
    if (nextIndex < 0 || nextIndex >= meta.num_rows) {
      setError(`Index out of range: ${nextIndex}`);
      return;
    }
    try {
      await loadRecord(meta.path, nextIndex);
      const nextOffset = Math.floor(nextIndex / PAGE_SIZE) * PAGE_SIZE;
      if (nextOffset !== pageOffset) await loadPage(meta.path, nextOffset);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function hydrateCachedTranslations(nextRecord: JsonlRecord) {
    const primaryEntries = Object.entries(nextRecord.record).filter(
      ([field, value]) => typeof value === "string" && isPrimaryTextField(field),
    ) as Array<[string, string]>;
    for (const [field, value] of primaryEntries) {
      try {
        const cached = await api.getCachedTranslation(nextRecord.dataset_id, nextRecord.index, field, value);
        if (cached.cached && cached.translation_zh) {
          setTranslations((current) => ({
            ...current,
            [translationKey(nextRecord.dataset_id, nextRecord.index, field)]: cached.translation_zh,
          }));
        }
      } catch {
        // Cache lookup is best-effort; explicit translation still reports failures.
      }
    }
  }

  async function translateField(fieldName: string, value: string) {
    if (!record) return;
    clearNotices();
    setAiBusy(true);
    try {
      const response = await api.translateField(record.dataset_id, record.index, fieldName, value, record.record);
      setTranslations((current) => ({
        ...current,
        [translationKey(record.dataset_id, record.index, fieldName)]: response.translation_zh,
      }));
      setMessage(response.cached ? "Loaded cached Chinese translation." : "Chinese translation saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setAiBusy(false);
    }
  }

  async function changePage(delta: number) {
    if (!meta) return;
    const maxOffset = Math.floor(Math.max(0, meta.num_rows - 1) / PAGE_SIZE) * PAGE_SIZE;
    const nextOffset = Math.max(0, Math.min(pageOffset + delta, maxOffset));
    try {
      await loadPage(meta.path, nextOffset);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  function clearNotices() {
    setError("");
    setMessage("");
  }

  return (
    <>
      {(message || error) && (
        <div className={`notice ${error ? "notice-error" : "notice-success"}`}>
          {error || message}
        </div>
      )}
      <main className="three-column">
        <section className="dataset-sidebar">
          <div className="pane-header">
            <h2>JSONL File</h2>
          </div>
          <label>
            Path
            <textarea value={path} onChange={(event) => setPath(event.target.value)} rows={4} />
          </label>
          <button className="primary full-width" onClick={() => void loadJsonl()}>
            {buttonLabel(uiLang, "loadJsonl")}
          </button>

          {meta && (
            <div className="dataset-card active">
              <div className="dataset-title">{meta.path}</div>
              <dl>
                <dt>ID</dt>
                <dd>{meta.dataset_id}</dd>
                <dt>Format</dt>
                <dd>{meta.format}</dd>
                <dt>Rows</dt>
                <dd>{meta.num_rows.toLocaleString()}</dd>
                <dt>Fields</dt>
                <dd>{meta.fields.join(", ")}</dd>
              </dl>
            </div>
          )}

          {page && (
            <div className="record-index-list">
              <div className="pane-header compact">
                <h2>Records</h2>
                <span className="muted">
                  {page.offset + 1}-{Math.min(page.offset + PAGE_SIZE, page.num_rows)}
                </span>
              </div>
              {page.records.map((entry) => (
                <button
                  key={entry.index}
                  className={`record-index-button ${entry.index === index ? "active" : ""}`}
                  onClick={() => void navigate(entry.index)}
                >
                  <strong>{entry.record.item_id ? String(entry.record.item_id) : `#${entry.index}`}</strong>
                  <span>{entry.record.domain ? String(entry.record.domain) : entry.record.subject ? String(entry.record.subject) : "record"}</span>
                </button>
              ))}
              <div className="record-page-actions">
                <button onClick={() => void changePage(-PAGE_SIZE)} disabled={pageOffset <= 0}>
                  {buttonLabel(uiLang, "previousPage")}
                </button>
                <button onClick={() => void changePage(PAGE_SIZE)} disabled={!meta || pageOffset + PAGE_SIZE >= meta.num_rows}>
                  {buttonLabel(uiLang, "nextPage")}
                </button>
              </div>
            </div>
          )}
        </section>

        <RawRecordViewer
          uiLang={uiLang}
          title="JSONL Record"
          emptyMessage="Load a JSONL file to inspect curated rows."
          dataset={activeDataset}
          record={record}
          index={index}
          translations={translations}
          aiBusy={aiBusy}
          showOutputActions={false}
          onNavigate={navigate}
          onTranslateField={translateField}
        />

        <section className="right-pane jsonl-preview-pane">
          <div className="output-preview">
            <div className="pane-header compact">
              <h2>JSON Tree Preview</h2>
              {record && <span className="muted">index {record.index}</span>}
            </div>
            {record ? <JsonTreeView value={record.record} /> : <p className="muted">No JSONL record loaded.</p>}
          </div>
          {record && (
            <div className="output-preview">
              <div className="pane-header compact">
                <h2>Raw JSON</h2>
              </div>
              <pre className="json-preview">{JSON.stringify(record.record, null, 2)}</pre>
            </div>
          )}
        </section>
      </main>
    </>
  );
}

function translationKey(datasetId: string, recordIndex: number, fieldName: string): string {
  return `${datasetId}:${recordIndex}:${fieldName}`;
}

function isPrimaryTextField(field: string): boolean {
  const key = field.toLowerCase();
  return ["problem", "question", "prompt", "stem"].some((candidate) => key.includes(candidate));
}
