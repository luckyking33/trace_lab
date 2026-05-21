from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from dataset_loader import DatasetLoadError, DatasetRegistry
from deepseek_client import DeepSeekError, call_deepseek, parse_json_object
from jsonl_loader import JsonlLoader, JsonlLoadError
from jsonl_writer import JsonlWriter, JsonlWriterError
from leakage_guard import load_forbidden_keys
from models import (
    AppendOutputRequest,
    AppendOutputResponse,
    CreateWorkspaceRequest,
    DraftLocator,
    DraftRequest,
    GenerateDraftRequest,
    GenerateDraftResponse,
    JsonlMetaResponse,
    JsonlRecordResponse,
    JsonlRecordsResponse,
    LoadDatasetRequest,
    LoadedDataset,
    OutputConfigRequest,
    SourceMetadataTranslationRequest,
    SourceMetadataTranslationResponse,
    TranslateFieldRequest,
    TranslateFieldResponse,
    UpdateWorkspaceRequest,
    ValidateOutputRequest,
)
from path_security import PathSecurityError, display_path, repo_root_from_backend, safe_output_path
from translation_store import TranslationStore
from validator import OutputValidator
from workspace_store import WorkspaceStore


REPO_ROOT = repo_root_from_backend()
FORBIDDEN_KEYS = load_forbidden_keys(REPO_ROOT)

app = FastAPI(title="Mechanism DG Data Curation UI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workspace_store = WorkspaceStore(REPO_ROOT)
dataset_registry = DatasetRegistry(REPO_ROOT, FORBIDDEN_KEYS)
output_validator = OutputValidator(REPO_ROOT, FORBIDDEN_KEYS)
jsonl_writer = JsonlWriter(REPO_ROOT)
jsonl_loader = JsonlLoader(REPO_ROOT, FORBIDDEN_KEYS)
translation_store = TranslationStore(REPO_ROOT)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "repo_root": str(REPO_ROOT)}


@app.post("/api/workspaces")
def create_workspace(request: CreateWorkspaceRequest):
    return workspace_store.create(request)


@app.get("/api/workspaces")
def list_workspaces():
    return workspace_store.list()


@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    try:
        return workspace_store.get(workspace_id)
    except KeyError as exc:
        raise http_error(404, exc)


@app.put("/api/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, request: UpdateWorkspaceRequest):
    try:
        return workspace_store.update(workspace_id, request)
    except KeyError as exc:
        raise http_error(404, exc)


@app.delete("/api/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str) -> dict[str, bool]:
    try:
        workspace_store.delete(workspace_id)
        return {"deleted": True}
    except KeyError as exc:
        raise http_error(404, exc)


@app.post("/api/datasets/load")
def load_dataset(request: LoadDatasetRequest):
    try:
        workspace_store.get(request.workspace_id)
        ref = dataset_registry.load(request.path)
        summary = dataset_registry.summary_from_ref(ref)
        dataset = LoadedDataset.model_validate(summary.model_dump())
        workspace_store.add_dataset(request.workspace_id, dataset)
        return dataset
    except (KeyError, PathSecurityError, DatasetLoadError) as exc:
        raise http_error(400, exc)


@app.get("/api/datasets/{dataset_id}/meta")
def dataset_meta(dataset_id: str):
    try:
        ensure_dataset_loaded(dataset_id)
        return dataset_registry.meta(dataset_id)
    except KeyError as exc:
        raise http_error(404, exc)


@app.get("/api/datasets/{dataset_id}/record/{index}")
def dataset_record(dataset_id: str, index: int):
    try:
        ensure_dataset_loaded(dataset_id)
        return dataset_registry.record(dataset_id, index)
    except KeyError as exc:
        raise http_error(404, exc)
    except IndexError as exc:
        raise http_error(400, exc)


@app.get("/api/datasets/{dataset_id}/records")
def dataset_records(dataset_id: str, offset: int = 0, limit: int = Query(default=20, le=100)):
    try:
        ensure_dataset_loaded(dataset_id)
        return dataset_registry.records(dataset_id, offset, limit)
    except KeyError as exc:
        raise http_error(404, exc)


@app.get("/api/jsonl/meta")
def jsonl_meta(path: str):
    try:
        return JsonlMetaResponse.model_validate(jsonl_loader.meta(path))
    except (PathSecurityError, JsonlLoadError) as exc:
        raise http_error(400, exc)


@app.get("/api/jsonl/record/{index}")
def jsonl_record(index: int, path: str):
    try:
        return JsonlRecordResponse.model_validate(jsonl_loader.record(path, index))
    except (PathSecurityError, JsonlLoadError) as exc:
        raise http_error(400, exc)
    except IndexError as exc:
        raise http_error(400, exc)


@app.get("/api/jsonl/records")
def jsonl_records(path: str, offset: int = 0, limit: int = Query(default=20, le=100)):
    try:
        return JsonlRecordsResponse.model_validate(jsonl_loader.records(path, offset, limit))
    except (PathSecurityError, JsonlLoadError) as exc:
        raise http_error(400, exc)
    except IndexError as exc:
        raise http_error(400, exc)


@app.post("/api/output/config")
def output_config(request: OutputConfigRequest):
    try:
        path = safe_output_path(
            request.output_directory,
            request.output_filename,
            REPO_ROOT,
            create_dir=request.create_dir,
        )
        if request.workspace_id:
            workspace_store.update(
                request.workspace_id,
                UpdateWorkspaceRequest(
                    output_directory=display_path(path.parent, REPO_ROOT),
                    output_filename=path.name,
                ),
            )
        return jsonl_writer.status(display_path(path, REPO_ROOT))
    except (PathSecurityError, KeyError, JsonlWriterError) as exc:
        raise http_error(400, exc)


@app.get("/api/output/status")
def output_status(path: str):
    try:
        return jsonl_writer.status(path)
    except (PathSecurityError, JsonlWriterError) as exc:
        raise http_error(400, exc)


@app.post("/api/output/validate")
def output_validate(request: ValidateOutputRequest):
    return output_validator.validate(request.item, request.output_path)


@app.post("/api/output/append")
def output_append(request: AppendOutputRequest):
    validation = output_validator.validate_for_append(request.item, request.output_path)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=[issue.model_dump() for issue in validation.errors])
    try:
        count = jsonl_writer.append(
            request.output_path,
            request.item,
            workspace_id=request.workspace_id,
            source_dataset_id=request.source_dataset_id,
            source_record_index=request.source_record_index,
        )
        return AppendOutputResponse(
            appended_item_id=request.item["item_id"],
            output_path=request.output_path,
            item_count=count,
        )
    except (PathSecurityError, JsonlWriterError) as exc:
        raise http_error(400, exc)


@app.post("/api/drafts/save")
def save_draft(request: DraftRequest):
    return workspace_store.save_draft(request)


@app.get("/api/drafts/load")
def load_draft(workspace_id: str, dataset_id: str, record_index: int):
    try:
        return workspace_store.load_draft(
            DraftLocator(workspace_id=workspace_id, dataset_id=dataset_id, record_index=record_index)
        )
    except KeyError as exc:
        raise http_error(404, exc)


@app.delete("/api/drafts/delete")
def delete_draft(workspace_id: str, dataset_id: str, record_index: int):
    deleted = workspace_store.delete_draft(
        DraftLocator(workspace_id=workspace_id, dataset_id=dataset_id, record_index=record_index)
    )
    return {"deleted": deleted}


@app.get("/api/ai/translation")
def get_cached_translation(dataset_id: str, record_index: int, field_name: str, text: str):
    cached = translation_store.load_field_translation(dataset_id, record_index, field_name, text)
    if not cached:
        return {"cached": False, "translation_zh": ""}
    return {
        "cached": True,
        "translation_zh": cached.get("translation_zh", ""),
        "dataset_id": dataset_id,
        "record_index": record_index,
        "field_name": field_name,
    }


@app.post("/api/ai/translate-field")
def translate_field(request: TranslateFieldRequest):
    cached = translation_store.load_field_translation(
        request.dataset_id, request.record_index, request.field_name, request.text
    )
    if cached:
        return TranslateFieldResponse(
            dataset_id=request.dataset_id,
            record_index=request.record_index,
            field_name=request.field_name,
            translation_zh=str(cached.get("translation_zh", "")),
            cached=True,
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a precise STEM translator. Translate the target English problem field into "
                "clear Simplified Chinese for a research data curation UI. Preserve mathematical notation, "
                "variables, units, equations, LaTeX, and answer references. Return only JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "Return JSON with exactly this shape: {\"translation_zh\": \"...\"}.\n\n"
                f"Field name: {request.field_name}\n"
                f"Target text:\n{request.text}\n\n"
                f"Full raw record context:\n{request.record_context}"
            ),
        },
    ]
    try:
        parsed = parse_json_object(call_deepseek(REPO_ROOT, messages))
    except DeepSeekError as exc:
        raise http_error(400, exc)
    translation = str(parsed.get("translation_zh", "")).strip()
    if not translation:
        raise http_error(400, DeepSeekError("DeepSeek returned an empty translation_zh"))
    translation_store.save_field_translation(
        request.dataset_id,
        request.record_index,
        request.field_name,
        request.text,
        translation,
    )
    return TranslateFieldResponse(
        dataset_id=request.dataset_id,
        record_index=request.record_index,
        field_name=request.field_name,
        translation_zh=translation,
        cached=False,
    )


@app.post("/api/ai/translate-source-metadata")
def translate_source_metadata(request: SourceMetadataTranslationRequest):
    cache_key = translation_store.metadata_cache_key(request.model_dump())
    cached = translation_store.load_metadata_translation(cache_key)
    if cached:
        return SourceMetadataTranslationResponse(fields=cached.get("fields", {}), cached=True)

    fields = ["item_id", "source_dataset", "source_split", "source_family", "source_record_id", "license_note"]
    messages = [
        {
            "role": "system",
            "content": (
                "You convert Chinese curation metadata into concise English mechanism-ready JSONL fields. "
                "Use the raw source problem and solution only as context. Do not invent research content. "
                "Preserve identifiers and dataset codes when already provided. Return only JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "Return JSON with exactly these string keys: "
                f"{fields}.\n"
                "Use Chinese metadata as the primary input. If a Chinese field is empty but current English "
                "already has a good value, keep the current English value. If neither is available, return an "
                "empty string for that key.\n\n"
                f"Chinese metadata fields:\n{request.source_metadata_zh}\n\n"
                f"Current English fields:\n{request.current_english}\n\n"
                f"Raw source record context:\n{request.raw_record}"
            ),
        },
    ]
    try:
        parsed = parse_json_object(call_deepseek(REPO_ROOT, messages))
    except DeepSeekError as exc:
        raise http_error(400, exc)
    translated = {field: str(parsed.get(field, "")).strip() for field in fields}
    translation_store.save_metadata_translation(cache_key, translated)
    return SourceMetadataTranslationResponse(fields=translated, cached=False)


@app.post("/api/ai/generate-draft")
def generate_draft(request: GenerateDraftRequest):
    messages = [
        {
            "role": "system",
            "content": (
                "You draft mechanism-ready JSONL annotations for a local research curation UI. "
                "Return only one JSON object with key \"item\". The item must use English-only values, "
                "match the provided output schema, and contain no original options, choices, distractors, "
                "human response distributions, seed candidates, or student-choice data. You may use the raw "
                "problem and solution as context, but do not invent source provenance."
            ),
        },
        {
            "role": "user",
            "content": (
                "Generate a complete draft item for manual review. The researcher will edit and verify it; "
                "do not claim final verification. Still, set quality_control booleans to false unless the "
                "raw source explicitly proves them. Include at least 3 solution_trace steps, at least 3 "
                "allowed_operator_ids, and at least 3 counterfactual_transforms. Keep all fields English.\n\n"
                "Required output shape:\n"
                "{\n"
                "  \"item\": {\n"
                "    \"item_id\": \"...\",\n"
                "    \"source_dataset\": \"...\",\n"
                "    \"source_split\": \"...\",\n"
                "    \"source_family\": \"...\",\n"
                "    \"source_record_id\": \"...\",\n"
                "    \"license_note\": \"...\",\n"
                "    \"subject\": \"math|physics\",\n"
                "    \"domain\": \"...\",\n"
                "    \"curriculum_level\": \"elementary|middle_school|high_school|undergraduate_intro|advanced\",\n"
                "    \"question_clean\": \"...\",\n"
                "    \"question_original_available\": false,\n"
                "    \"modification_level\": \"original_clean|numeric_perturbation|paraphrased|structure_preserved|manual_rewrite\",\n"
                "    \"correct_answer\": \"...\",\n"
                "    \"answer_type\": \"numeric|formula|unit_quantity|vector|finite_set|conceptual_binary\",\n"
                "    \"answer_format\": {\"type\": \"...\", \"unit\": null, \"precision\": null},\n"
                "    \"construct\": {\"primary\": \"...\", \"secondary\": [\"...\"]},\n"
                "    \"givens\": [{\"symbol\": \"...\", \"value\": \"...\"}],\n"
                "    \"variables\": [{\"symbol\": \"...\", \"role\": \"...\", \"domain\": \"...\"}],\n"
                "    \"constraints\": [{\"type\": \"...\", \"target\": \"...\", \"value\": \"...\"}],\n"
                "    \"solution_trace\": [{\"step_id\": 1, \"premise\": \"...\", \"operation\": \"...\", \"expr_before\": null, \"expr_after\": \"...\", \"verifier_hint\": \"...\"}],\n"
                "    \"valid_answer_set\": {\"type\": \"...\", \"value\": \"...\", \"tolerance\": null},\n"
                "    \"allowed_operator_ids\": [\"ALG_SIGN_MOVE\", \"ALG_DISTRIBUTIVE_DROP\", \"ALG_ILLEGAL_CANCEL\"],\n"
                "    \"operator_precondition_notes\": {\"ALG_SIGN_MOVE\": \"...\"},\n"
                "    \"counterfactual_transforms\": [{\"type\": \"...\", \"description\": \"...\", \"answer_mapping\": \"...\"}],\n"
                "    \"leakage_flags\": {\"used_original_distractors\": false, \"used_human_response_dist\": false, \"used_seed_candidates\": false, \"original_options_removed\": true},\n"
                "    \"quality_control\": {\"manual_checked\": false, \"answer_verified\": false, \"trace_verified\": false, \"operator_applicability_checked\": false, \"counterfactual_ready\": false, \"notes\": \"AI draft; requires manual review.\"}\n"
                "  }\n"
                "}\n\n"
                f"Dataset context:\n{request.dataset}\n\n"
                f"Current partial item:\n{request.current_item}\n\n"
                f"Chinese translation of problem if available:\n{request.problem_translation_zh}\n\n"
                f"Raw source record:\n{request.raw_record}"
            ),
        },
    ]
    try:
        parsed = parse_json_object(call_deepseek(REPO_ROOT, messages, temperature=0.1))
    except DeepSeekError as exc:
        raise http_error(400, exc)
    item = parsed.get("item")
    if not isinstance(item, dict):
        raise http_error(400, DeepSeekError("DeepSeek response missing object field: item"))
    quality_control = item.get("quality_control") if isinstance(item.get("quality_control"), dict) else {}
    quality_control.update(
        {
            "manual_checked": False,
            "answer_verified": False,
            "trace_verified": False,
            "operator_applicability_checked": False,
            "counterfactual_ready": False,
            "notes": str(quality_control.get("notes") or "AI draft; requires manual review."),
        }
    )
    item["quality_control"] = quality_control

    leakage_flags = item.get("leakage_flags") if isinstance(item.get("leakage_flags"), dict) else {}
    leakage_flags.update(
        {
            "used_original_distractors": False,
            "used_human_response_dist": False,
            "used_seed_candidates": False,
            "original_options_removed": True,
        }
    )
    item["leakage_flags"] = leakage_flags
    return GenerateDraftResponse(item=item)


def http_error(status_code: int, exc: Exception) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def ensure_dataset_loaded(dataset_id: str) -> None:
    try:
        dataset_registry.meta(dataset_id)
        return
    except KeyError:
        pass
    for workspace in workspace_store.list():
        for dataset in workspace.loaded_input_datasets:
            if dataset.dataset_id == dataset_id:
                dataset_registry.load(dataset.path)
                return
    raise KeyError(f"Dataset is not loaded and no workspace metadata points to it: {dataset_id}")
