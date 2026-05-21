export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8766";

export interface DatasetSummary {
  dataset_id: string;
  path: string;
  format: string;
  num_rows: number;
  fields: string[];
  field_types: Record<string, string>;
}

export interface Workspace {
  workspace_id: string;
  workspace_name: string;
  loaded_input_datasets: DatasetSummary[];
  active_dataset_id: string | null;
  output_directory: string;
  output_filename: string;
  last_viewed_record_index: number;
  editor_draft_state: Record<string, unknown>;
}

export interface DatasetRecord {
  dataset_id: string;
  index: number;
  num_rows: number;
  record: Record<string, unknown>;
  leakage_warnings: string[];
}

export interface JsonlMeta extends DatasetSummary {
  format: "jsonl";
}

export interface JsonlRecord extends DatasetRecord {
  path: string;
}

export interface JsonlRecordsPage {
  dataset_id: string;
  path: string;
  offset: number;
  limit: number;
  num_rows: number;
  records: Array<{ index: number; record: Record<string, unknown>; leakage_warnings: string[] }>;
}

export interface ValidationIssue {
  severity: "error" | "warning";
  path: string;
  message: string;
}

export interface ValidationResponse {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface OutputStatus {
  output_path: string;
  exists: boolean;
  item_count: number;
  last_item_id: string | null;
}

export type UiLanguage = "en" | "zh";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = payload?.detail ?? payload ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload as T;
}

export const api = {
  listWorkspaces: () => request<Workspace[]>("/api/workspaces"),
  createWorkspace: (workspace_name: string) =>
    request<Workspace>("/api/workspaces", {
      method: "POST",
      body: JSON.stringify({ workspace_name }),
    }),
  updateWorkspace: (workspaceId: string, patch: Partial<Workspace>) =>
    request<Workspace>(`/api/workspaces/${workspaceId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteWorkspace: (workspaceId: string) =>
    request<{ deleted: boolean }>(`/api/workspaces/${workspaceId}`, { method: "DELETE" }),
  loadDataset: (workspace_id: string, path: string) =>
    request<DatasetSummary>("/api/datasets/load", {
      method: "POST",
      body: JSON.stringify({ workspace_id, path }),
    }),
  getRecord: (datasetId: string, index: number) =>
    request<DatasetRecord>(`/api/datasets/${datasetId}/record/${index}`),
  getRecords: (datasetId: string, offset = 0, limit = 20) =>
    request(`/api/datasets/${datasetId}/records?offset=${offset}&limit=${limit}`),
  getJsonlMeta: (path: string) =>
    request<JsonlMeta>(`/api/jsonl/meta?path=${encodeURIComponent(path)}`),
  getJsonlRecord: (path: string, index: number) =>
    request<JsonlRecord>(`/api/jsonl/record/${index}?path=${encodeURIComponent(path)}`),
  getJsonlRecords: (path: string, offset = 0, limit = 20) =>
    request<JsonlRecordsPage>(`/api/jsonl/records?path=${encodeURIComponent(path)}&offset=${offset}&limit=${limit}`),
  configureOutput: (workspace_id: string, output_directory: string, output_filename: string, create_dir: boolean) =>
    request<OutputStatus>("/api/output/config", {
      method: "POST",
      body: JSON.stringify({ workspace_id, output_directory, output_filename, create_dir }),
    }),
  outputStatus: (path: string) =>
    request<OutputStatus>(`/api/output/status?path=${encodeURIComponent(path)}`),
  validateOutput: (item: Record<string, unknown>, output_path?: string) =>
    request<ValidationResponse>("/api/output/validate", {
      method: "POST",
      body: JSON.stringify({ item, output_path }),
    }),
  appendOutput: (
    item: Record<string, unknown>,
    output_path: string,
    workspace_id?: string,
    source_dataset_id?: string,
    source_record_index?: number,
  ) =>
    request("/api/output/append", {
      method: "POST",
      body: JSON.stringify({ item, output_path, workspace_id, source_dataset_id, source_record_index }),
    }),
  saveDraft: (workspace_id: string, dataset_id: string, record_index: number, item: Record<string, unknown>) =>
    request("/api/drafts/save", {
      method: "POST",
      body: JSON.stringify({ workspace_id, dataset_id, record_index, item }),
    }),
  loadDraft: (workspace_id: string, dataset_id: string, record_index: number) =>
    request<{ item: Record<string, unknown> }>(
      `/api/drafts/load?workspace_id=${workspace_id}&dataset_id=${dataset_id}&record_index=${record_index}`,
    ),
  deleteDraft: (workspace_id: string, dataset_id: string, record_index: number) =>
    request<{ deleted: boolean }>(
      `/api/drafts/delete?workspace_id=${workspace_id}&dataset_id=${dataset_id}&record_index=${record_index}`,
      {
        method: "DELETE",
      },
    ),
  getCachedTranslation: (dataset_id: string, record_index: number, field_name: string, text: string) =>
    request<{ cached: boolean; translation_zh: string }>(
      `/api/ai/translation?dataset_id=${encodeURIComponent(dataset_id)}&record_index=${record_index}&field_name=${encodeURIComponent(field_name)}&text=${encodeURIComponent(text)}`,
    ),
  translateField: (
    dataset_id: string,
    record_index: number,
    field_name: string,
    text: string,
    record_context: Record<string, unknown>,
  ) =>
    request<{ translation_zh: string; cached: boolean }>("/api/ai/translate-field", {
      method: "POST",
      body: JSON.stringify({ dataset_id, record_index, field_name, text, record_context }),
    }),
  translateSourceMetadata: (
    source_metadata_zh: Record<string, string>,
    current_english: Record<string, string>,
    raw_record: Record<string, unknown>,
  ) =>
    request<{ fields: Record<string, string>; cached: boolean }>("/api/ai/translate-source-metadata", {
      method: "POST",
      body: JSON.stringify({ source_metadata_zh, current_english, raw_record }),
    }),
  generateDraft: (
    raw_record: Record<string, unknown>,
    dataset: Record<string, unknown>,
    current_item: Record<string, unknown>,
    problem_translation_zh: string,
  ) =>
    request<{ item: Record<string, unknown> }>("/api/ai/generate-draft", {
      method: "POST",
      body: JSON.stringify({ raw_record, dataset, current_item, problem_translation_zh }),
    }),
};

export function buttonLabel(lang: UiLanguage, key: string): string {
  const zh: Record<string, string> = {
    new: "新建",
    delete: "删除",
    setOutput: "设置输出",
    reload: "刷新",
    loadDataset: "+ 加载数据集",
    remove: "移除",
    previous: "上一条",
    next: "下一条",
    go: "跳转",
    copyValue: "复制值",
    copyQuestion: "复制到题目",
    copyRecordRef: "复制记录引用",
    translateProblem: "AI 中文翻译",
    saveDraft: "保存草稿",
    loadDraft: "加载草稿",
    clearDraft: "清空草稿",
    confirmAdd: "确认写入 JSONL",
    aiTranslateEnglish: "AI 转英文",
    generateDraft: "AI 生成标注草稿",
    add: "添加",
    addGiven: "添加 given",
    addVariable: "添加 variable",
    addConstraint: "添加 constraint",
    addStep: "添加 step",
    addTransform: "添加 transform",
    removeStep: "移除 step",
    toggleChinese: "中文按钮",
    toggleEnglish: "English Buttons",
    dataCurationPage: "数据处理",
    jsonlViewerPage: "JSONL 查看",
    loadJsonl: "加载 JSONL",
    previousPage: "上一页",
    nextPage: "下一页",
  };
  const en: Record<string, string> = {
    new: "New",
    delete: "Delete",
    setOutput: "Set Output",
    reload: "Reload",
    loadDataset: "+ Load Dataset",
    remove: "Remove",
    previous: "Previous",
    next: "Next",
    go: "Go",
    copyValue: "Copy value",
    copyQuestion: "Copy to question",
    copyRecordRef: "Copy record ref",
    translateProblem: "AI Chinese translation",
    saveDraft: "Save Draft",
    loadDraft: "Load Draft",
    clearDraft: "Clear Draft",
    confirmAdd: "Confirm Add to JSONL",
    aiTranslateEnglish: "AI to English",
    generateDraft: "AI annotation draft",
    add: "Add",
    addGiven: "Add given",
    addVariable: "Add variable",
    addConstraint: "Add constraint",
    addStep: "Add step",
    addTransform: "Add transform",
    removeStep: "Remove step",
    toggleChinese: "中文按钮",
    toggleEnglish: "English Buttons",
    dataCurationPage: "Data curation",
    jsonlViewerPage: "JSONL viewer",
    loadJsonl: "Load JSONL",
    previousPage: "Previous page",
    nextPage: "Next page",
  };
  return (lang === "zh" ? zh : en)[key] ?? key;
}
