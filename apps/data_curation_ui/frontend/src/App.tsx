import { useEffect, useMemo, useState } from "react";
import { api, buttonLabel, DatasetRecord, DatasetSummary, OutputStatus, UiLanguage, ValidationResponse, Workspace } from "./api";
import WorkspaceBar from "./components/WorkspaceBar";
import DatasetSidebar from "./components/DatasetSidebar";
import RawRecordViewer from "./components/RawRecordViewer";
import OutputItemEditor, { defaultItem, MechanismItem } from "./components/OutputItemEditor";
import ValidationPanel from "./components/ValidationPanel";
import OutputPreview from "./components/OutputPreview";
import JsonlViewerPage from "./components/JsonlViewerPage";

type AppPage = "curation" | "jsonl";

export default function App() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string>("");
  const [record, setRecord] = useState<DatasetRecord | null>(null);
  const [recordIndex, setRecordIndex] = useState(0);
  const [item, setItem] = useState<MechanismItem>(defaultItem());
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [outputStatus, setOutputStatus] = useState<OutputStatus | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [uiLang, setUiLang] = useState<UiLanguage>("en");
  const [translations, setTranslations] = useState<Record<string, string>>({});
  const [aiBusy, setAiBusy] = useState(false);
  const [activePage, setActivePage] = useState<AppPage>("curation");

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.workspace_id === activeWorkspaceId) ?? null,
    [workspaces, activeWorkspaceId],
  );

  const activeDataset = useMemo<DatasetSummary | null>(() => {
    if (!activeWorkspace?.active_dataset_id) return null;
    return (
      activeWorkspace.loaded_input_datasets.find(
        (dataset) => dataset.dataset_id === activeWorkspace.active_dataset_id,
      ) ?? null
    );
  }, [activeWorkspace]);

  const outputPath = useMemo(() => {
    if (!activeWorkspace?.output_directory || !activeWorkspace.output_filename) return "";
    return `${activeWorkspace.output_directory.replace(/\/$/, "")}/${activeWorkspace.output_filename}`;
  }, [activeWorkspace]);

  useEffect(() => {
    void refreshWorkspaces();
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void validate();
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [item, outputPath]);

  async function refreshWorkspaces(nextActiveId?: string) {
    const loaded = await api.listWorkspaces();
    setWorkspaces(loaded);
    if (nextActiveId) {
      setActiveWorkspaceId(nextActiveId);
    } else if (!activeWorkspaceId && loaded.length) {
      setActiveWorkspaceId(loaded[0].workspace_id);
    }
  }

  async function createWorkspace(name: string) {
    clearNotices();
    const workspace = await api.createWorkspace(name);
    await refreshWorkspaces(workspace.workspace_id);
    setMessage(`Workspace created: ${workspace.workspace_name}`);
  }

  async function deleteWorkspace(id: string) {
    clearNotices();
    await api.deleteWorkspace(id);
    setActiveWorkspaceId("");
    await refreshWorkspaces();
    setMessage("Workspace deleted.");
  }

  async function updateWorkspace(patch: Partial<Workspace>) {
    if (!activeWorkspace) return;
    clearNotices();
    const updated = await api.updateWorkspace(activeWorkspace.workspace_id, patch);
    setWorkspaces((current) =>
      current.map((workspace) => (workspace.workspace_id === updated.workspace_id ? updated : workspace)),
    );
  }

  async function loadDataset(path: string) {
    if (!activeWorkspace) return;
    clearNotices();
    const dataset = await api.loadDataset(activeWorkspace.workspace_id, path);
    await refreshWorkspaces(activeWorkspace.workspace_id);
    setRecordIndex(0);
    await loadRecord(dataset.dataset_id, 0);
    setMessage(`Loaded ${dataset.num_rows} rows from ${dataset.path}`);
  }

  async function selectDataset(datasetId: string) {
    await updateWorkspace({ active_dataset_id: datasetId });
    setRecordIndex(0);
    await loadRecord(datasetId, 0);
  }

  async function removeDataset(datasetId: string) {
    if (!activeWorkspace) return;
    const datasets = activeWorkspace.loaded_input_datasets.filter((dataset) => dataset.dataset_id !== datasetId);
    const nextActive = activeWorkspace.active_dataset_id === datasetId ? datasets[0]?.dataset_id ?? null : activeWorkspace.active_dataset_id;
    await updateWorkspace({ loaded_input_datasets: datasets, active_dataset_id: nextActive });
    if (nextActive) {
      await loadRecord(nextActive, 0);
    } else {
      setRecord(null);
    }
  }

  async function loadRecord(datasetId: string, index: number) {
    clearNotices();
    const nextRecord = await api.getRecord(datasetId, index);
    setRecord(nextRecord);
    setRecordIndex(index);
    void hydrateCachedTranslations(nextRecord);
    if (activeWorkspace) {
      await api.updateWorkspace(activeWorkspace.workspace_id, { last_viewed_record_index: index });
    }
  }

  async function navigate(nextIndex: number) {
    if (!activeDataset) return;
    if (dirty) {
      const shouldSave = window.confirm("You have unsaved changes. Save draft before navigating?");
      if (shouldSave) await saveDraft();
    }
    if (nextIndex < 0 || nextIndex >= activeDataset.num_rows) {
      setError(`Index out of range: ${nextIndex}`);
      return;
    }
    await loadRecord(activeDataset.dataset_id, nextIndex);
  }

  async function configureOutput(directory: string, filename: string, createDir: boolean) {
    if (!activeWorkspace) return;
    clearNotices();
    const status = await api.configureOutput(activeWorkspace.workspace_id, directory, filename, createDir);
    await refreshWorkspaces(activeWorkspace.workspace_id);
    setOutputStatus(status);
    setMessage(`Output configured: ${status.output_path}`);
  }

  async function refreshOutputStatus() {
    if (!outputPath) return;
    clearNotices();
    setOutputStatus(await api.outputStatus(outputPath));
  }

  async function validate() {
    const response = await api.validateOutput(toOutputItem(item), outputPath || undefined);
    setValidation(response);
  }

  async function appendItem() {
    if (!outputPath || !activeWorkspace) {
      setError("Configure an output JSONL path before appending.");
      return;
    }
    clearNotices();
    const outputItem = toOutputItem(item);
    const local = await api.validateOutput(outputItem, outputPath);
    setValidation(local);
    if (!local.valid) {
      setError("Fix validation errors before appending.");
      return;
    }
    const response = (await api.appendOutput(
      outputItem,
      outputPath,
      activeWorkspace.workspace_id,
      activeDataset?.dataset_id,
      recordIndex,
    )) as { appended_item_id: string; item_count: number; output_path: string };
    setDirty(false);
    setMessage(`Appended ${response.appended_item_id}; output now has ${response.item_count} items.`);
    await refreshOutputStatus();
  }

  async function saveDraft() {
    if (!activeWorkspace || !activeDataset) return;
    clearNotices();
    await api.saveDraft(activeWorkspace.workspace_id, activeDataset.dataset_id, recordIndex, item as unknown as Record<string, unknown>);
    setDirty(false);
    setMessage("Draft saved.");
  }

  async function loadDraft() {
    if (!activeWorkspace || !activeDataset) return;
    clearNotices();
    const draft = await api.loadDraft(activeWorkspace.workspace_id, activeDataset.dataset_id, recordIndex);
    setItem(draft.item as unknown as MechanismItem);
    setDirty(false);
    setMessage("Draft loaded.");
  }

  async function clearDraft() {
    if (!activeWorkspace || !activeDataset) return;
    const confirmed = window.confirm("Clear the current editor draft and remove the saved draft for this source record?");
    if (!confirmed) return;
    clearNotices();
    const response = await api.deleteDraft(activeWorkspace.workspace_id, activeDataset.dataset_id, recordIndex);
    setItem(defaultItemForRecord(activeDataset, recordIndex, record));
    setDirty(false);
    setMessage(response.deleted ? "Draft cleared and saved draft deleted." : "Draft cleared. No saved draft existed on disk.");
  }

  function updateItem(next: MechanismItem) {
    setItem(next);
    setDirty(true);
  }

  function copyToOutput(field: keyof MechanismItem, value: unknown) {
    updateItem({ ...item, [field]: String(value ?? "") });
  }

  async function hydrateCachedTranslations(nextRecord: DatasetRecord) {
    const problem = nextRecord.record.problem;
    if (typeof problem !== "string" || !problem.trim()) return;
    try {
      const cached = await api.getCachedTranslation(nextRecord.dataset_id, nextRecord.index, "problem", problem);
      if (cached.cached && cached.translation_zh) {
        setTranslations((current) => ({
          ...current,
          [translationKey(nextRecord.dataset_id, nextRecord.index, "problem")]: cached.translation_zh,
        }));
      }
    } catch {
      // Cache lookup is best-effort; the explicit translate button still reports API errors.
    }
  }

  async function translateRawField(fieldName: string, value: string) {
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

  async function translateSourceMetadata() {
    clearNotices();
    setAiBusy(true);
    try {
      const response = await api.translateSourceMetadata(
        item.source_metadata_zh ?? {},
        pickSourceMetadata(item),
        record?.record ?? {},
      );
      const nonEmptyFields = Object.fromEntries(
        Object.entries(response.fields).filter(([, value]) => value.trim().length > 0),
      );
      updateItem({ ...item, ...nonEmptyFields });
      setMessage(response.cached ? "Loaded cached English metadata." : "English metadata filled by DeepSeek.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setAiBusy(false);
    }
  }

  async function generateAnnotationDraft() {
    if (!record) {
      setError("Load a source record before generating an annotation draft.");
      return;
    }
    clearNotices();
    setAiBusy(true);
    try {
      const problemTranslation =
        translations[translationKey(record.dataset_id, record.index, "problem")] ??
        translations[translationKey(record.dataset_id, record.index, "question")] ??
        "";
      const response = await api.generateDraft(
        record.record,
        activeDataset ? (activeDataset as unknown as Record<string, unknown>) : {},
        toOutputItem(item),
        problemTranslation,
      );
      const sourceZh = item.source_metadata_zh;
      setItem({ ...item, ...(response.item as unknown as Partial<MechanismItem>), source_metadata_zh: sourceZh });
      setDirty(true);
      setMessage("AI annotation draft filled. Please manually review every field before append.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setAiBusy(false);
    }
  }

  function clearNotices() {
    setError("");
    setMessage("");
  }

  return (
    <div className="app-shell">
      <WorkspaceBar
        uiLang={uiLang}
        workspaces={workspaces}
        activeWorkspace={activeWorkspace}
        outputStatus={outputStatus}
        onSelect={setActiveWorkspaceId}
        onToggleLanguage={() => setUiLang((current) => (current === "en" ? "zh" : "en"))}
        onCreate={createWorkspace}
        onDelete={deleteWorkspace}
        onConfigureOutput={configureOutput}
        onRefreshOutput={refreshOutputStatus}
      />
      <nav className="page-switcher">
        <button className={activePage === "curation" ? "selected" : ""} onClick={() => setActivePage("curation")}>
          {buttonLabel(uiLang, "dataCurationPage")}
        </button>
        <button className={activePage === "jsonl" ? "selected" : ""} onClick={() => setActivePage("jsonl")}>
          {buttonLabel(uiLang, "jsonlViewerPage")}
        </button>
      </nav>
      {activePage === "curation" && (message || error) && (
        <div className={`notice ${error ? "notice-error" : "notice-success"}`}>
          {error || message}
        </div>
      )}
      {activePage === "curation" ? (
        <main className="three-column">
          <DatasetSidebar
            uiLang={uiLang}
            workspace={activeWorkspace}
            activeDatasetId={activeWorkspace?.active_dataset_id ?? null}
            onLoadDataset={loadDataset}
            onSelectDataset={selectDataset}
            onRemoveDataset={removeDataset}
          />
          <RawRecordViewer
            uiLang={uiLang}
            dataset={activeDataset}
            record={record}
            index={recordIndex}
            translations={translations}
            aiBusy={aiBusy}
            onNavigate={navigate}
            onCopyToOutput={copyToOutput}
            onTranslateField={translateRawField}
          />
          <section className="right-pane">
            <div className="editor-actions">
              <button onClick={saveDraft} disabled={!activeDataset}>{buttonLabel(uiLang, "saveDraft")}</button>
              <button onClick={loadDraft} disabled={!activeDataset}>{buttonLabel(uiLang, "loadDraft")}</button>
              <button onClick={clearDraft} disabled={!activeDataset}>{buttonLabel(uiLang, "clearDraft")}</button>
              <button onClick={generateAnnotationDraft} disabled={!record || aiBusy}>{buttonLabel(uiLang, "generateDraft")}</button>
              <button className="primary" onClick={appendItem}>{buttonLabel(uiLang, "confirmAdd")}</button>
            </div>
            <ValidationPanel validation={validation} rawWarnings={record?.leakage_warnings ?? []} />
            <OutputItemEditor
              item={item}
              uiLang={uiLang}
              aiBusy={aiBusy}
              onChange={updateItem}
              onTranslateSourceMetadata={translateSourceMetadata}
            />
            <OutputPreview item={item} outputStatus={outputStatus} />
          </section>
        </main>
      ) : (
        <JsonlViewerPage uiLang={uiLang} />
      )}
    </div>
  );
}

function defaultItemForRecord(
  dataset: DatasetSummary | null,
  recordIndex: number,
  record: DatasetRecord | null,
): MechanismItem {
  const next = defaultItem();
  if (!dataset) return next;

  const rawType = typeof record?.record.type === "string" ? record.record.type : "";
  const path = dataset.path.toLowerCase();
  const split = path.includes("/test/") || path.includes("\\test\\") ? "test" : "train";
  next.source_split = split;
  next.source_record_id = `${dataset.dataset_id}:${recordIndex}`;

  if (path.includes("competition_math") || dataset.fields.includes("problem")) {
    next.source_dataset = "MATH";
    next.source_family = rawType ? `competition_math/${rawType.toLowerCase()}` : "competition_math";
    next.subject = "math";
    next.domain = rawType.toLowerCase();
  }

  return next;
}

function translationKey(datasetId: string, recordIndex: number, fieldName: string): string {
  return `${datasetId}:${recordIndex}:${fieldName}`;
}

function pickSourceMetadata(item: MechanismItem): Record<string, string> {
  return {
    item_id: item.item_id,
    source_dataset: item.source_dataset,
    source_split: item.source_split,
    source_family: item.source_family,
    source_record_id: item.source_record_id,
    license_note: item.license_note,
  };
}

function toOutputItem(item: MechanismItem): Record<string, unknown> {
  const { source_metadata_zh: _sourceMetadataZh, ...outputItem } = item;
  return outputItem as unknown as Record<string, unknown>;
}
