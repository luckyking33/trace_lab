import { useEffect, useState } from "react";
import { buttonLabel, OutputStatus, UiLanguage, Workspace } from "../api";

interface Props {
  uiLang: UiLanguage;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  outputStatus: OutputStatus | null;
  onSelect: (workspaceId: string) => void;
  onToggleLanguage: () => void;
  onCreate: (name: string) => Promise<void>;
  onDelete: (workspaceId: string) => Promise<void>;
  onConfigureOutput: (directory: string, filename: string, createDir: boolean) => Promise<void>;
  onRefreshOutput: () => Promise<void>;
}

export default function WorkspaceBar({
  uiLang,
  workspaces,
  activeWorkspace,
  outputStatus,
  onSelect,
  onToggleLanguage,
  onCreate,
  onDelete,
  onConfigureOutput,
  onRefreshOutput,
}: Props) {
  const [workspaceName, setWorkspaceName] = useState("MVP Curation");
  const [directory, setDirectory] = useState("data/derived_no_options");
  const [filename, setFilename] = useState("mechanism_toy_50.jsonl");
  const [createDir, setCreateDir] = useState(true);

  useEffect(() => {
    if (activeWorkspace) {
      setDirectory(activeWorkspace.output_directory || "data/derived_no_options");
      setFilename(activeWorkspace.output_filename || "mechanism_toy_50.jsonl");
    }
  }, [activeWorkspace]);

  async function handleCreate() {
    await onCreate(workspaceName);
  }

  async function handleDelete() {
    if (!activeWorkspace) return;
    const confirmed = window.confirm(`Delete workspace "${activeWorkspace.workspace_name}"? Draft files remain on disk.`);
    if (confirmed) await onDelete(activeWorkspace.workspace_id);
  }

  return (
    <header className="workspace-bar">
      <div className="workspace-group">
        <label>
          Workspace
          <select value={activeWorkspace?.workspace_id ?? ""} onChange={(event) => onSelect(event.target.value)}>
            <option value="" disabled>
              Select workspace
            </option>
            {workspaces.map((workspace) => (
              <option key={workspace.workspace_id} value={workspace.workspace_id}>
                {workspace.workspace_name}
              </option>
            ))}
          </select>
        </label>
        <input
          value={workspaceName}
          onChange={(event) => setWorkspaceName(event.target.value)}
          placeholder="New workspace name"
        />
        <button onClick={handleCreate}>{buttonLabel(uiLang, "new")}</button>
        <button onClick={handleDelete} disabled={!activeWorkspace} className="danger">
          {buttonLabel(uiLang, "delete")}
        </button>
        <button onClick={onToggleLanguage}>
          {uiLang === "en" ? buttonLabel(uiLang, "toggleChinese") : buttonLabel(uiLang, "toggleEnglish")}
        </button>
      </div>

      <div className="output-config">
        <label>
          Output directory
          <input value={directory} onChange={(event) => setDirectory(event.target.value)} />
        </label>
        <label>
          Output filename
          <input value={filename} onChange={(event) => setFilename(event.target.value)} />
        </label>
        <label className="checkbox-line">
          <input type="checkbox" checked={createDir} onChange={(event) => setCreateDir(event.target.checked)} />
          Create dir
        </label>
        <button onClick={() => onConfigureOutput(directory, filename, createDir)} disabled={!activeWorkspace}>
          {buttonLabel(uiLang, "setOutput")}
        </button>
        <button onClick={onRefreshOutput} disabled={!activeWorkspace}>
          {buttonLabel(uiLang, "reload")}
        </button>
        <div className="output-status">
          <strong>{outputStatus?.item_count ?? 0}</strong> items
          <span>{outputStatus?.last_item_id ? `last: ${outputStatus.last_item_id}` : "no last item"}</span>
        </div>
      </div>
    </header>
  );
}
