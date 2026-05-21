from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid4

from models import (
    CreateWorkspaceRequest,
    DraftLocator,
    DraftRequest,
    LoadedDataset,
    UpdateWorkspaceRequest,
    Workspace,
)


class WorkspaceStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.store_dir = repo_root / ".dg_curation"
        self.workspaces_path = self.store_dir / "workspaces.json"
        self.drafts_dir = self.store_dir / "drafts"

    def list(self) -> list[Workspace]:
        payload = self._read()
        return [Workspace.model_validate(item) for item in payload.get("workspaces", [])]

    def create(self, request: CreateWorkspaceRequest) -> Workspace:
        name = request.workspace_name.strip() or "Untitled Workspace"
        workspace = Workspace(workspace_id=f"ws_{uuid4().hex[:12]}", workspace_name=name)
        workspaces = self.list()
        workspaces.append(workspace)
        self._write(workspaces)
        return workspace

    def get(self, workspace_id: str) -> Workspace:
        for workspace in self.list():
            if workspace.workspace_id == workspace_id:
                return workspace
        raise KeyError(f"Workspace not found: {workspace_id}")

    def update(self, workspace_id: str, request: UpdateWorkspaceRequest) -> Workspace:
        workspaces = self.list()
        updated: Workspace | None = None
        for index, workspace in enumerate(workspaces):
            if workspace.workspace_id != workspace_id:
                continue
            data = workspace.model_dump()
            patch = request.model_dump(exclude_unset=True)
            data.update({key: value for key, value in patch.items() if value is not None})
            updated = Workspace.model_validate(data)
            workspaces[index] = updated
            break
        if updated is None:
            raise KeyError(f"Workspace not found: {workspace_id}")
        self._write(workspaces)
        return updated

    def delete(self, workspace_id: str) -> None:
        workspaces = [workspace for workspace in self.list() if workspace.workspace_id != workspace_id]
        if len(workspaces) == len(self.list()):
            raise KeyError(f"Workspace not found: {workspace_id}")
        self._write(workspaces)

    def add_dataset(self, workspace_id: str, dataset: LoadedDataset) -> Workspace:
        workspace = self.get(workspace_id)
        datasets = [item for item in workspace.loaded_input_datasets if item.dataset_id != dataset.dataset_id]
        datasets.append(dataset)
        return self.update(
            workspace_id,
            UpdateWorkspaceRequest(
                loaded_input_datasets=datasets,
                active_dataset_id=dataset.dataset_id,
            ),
        )

    def save_draft(self, request: DraftRequest) -> dict:
        path = self._draft_path(request.workspace_id, request.dataset_id, request.record_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = request.model_dump()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def load_draft(self, locator: DraftLocator) -> dict:
        path = self._draft_path(locator.workspace_id, locator.dataset_id, locator.record_index)
        if not path.exists():
            raise KeyError("Draft not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_draft(self, locator: DraftLocator) -> bool:
        path = self._draft_path(locator.workspace_id, locator.dataset_id, locator.record_index)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _read(self) -> dict:
        if not self.workspaces_path.exists():
            return {"workspaces": []}
        return json.loads(self.workspaces_path.read_text(encoding="utf-8"))

    def _write(self, workspaces: list[Workspace]) -> None:
        self.store_dir.mkdir(parents=True, exist_ok=True)
        payload = {"workspaces": [workspace.model_dump() for workspace in workspaces]}
        self.workspaces_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _draft_path(self, workspace_id: str, dataset_id: str, record_index: int) -> Path:
        safe_workspace = _safe_name(workspace_id)
        safe_dataset = _safe_name(dataset_id)
        return self.drafts_dir / safe_workspace / f"{safe_dataset}_{record_index}.json"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)
