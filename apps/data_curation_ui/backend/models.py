from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AnswerType = Literal[
    "numeric",
    "formula",
    "unit_quantity",
    "vector",
    "finite_set",
    "conceptual_binary",
]

ModificationLevel = Literal[
    "original_clean",
    "numeric_perturbation",
    "paraphrased",
    "structure_preserved",
    "manual_rewrite",
]

CurriculumLevel = Literal[
    "elementary",
    "middle_school",
    "high_school",
    "undergraduate_intro",
    "advanced",
]


class ApiError(BaseModel):
    detail: str


class DatasetSummary(BaseModel):
    dataset_id: str
    path: str
    format: str
    num_rows: int
    fields: list[str]
    field_types: dict[str, str] = Field(default_factory=dict)


class LoadedDataset(DatasetSummary):
    pass


class Workspace(BaseModel):
    workspace_id: str
    workspace_name: str
    loaded_input_datasets: list[LoadedDataset] = Field(default_factory=list)
    active_dataset_id: str | None = None
    output_directory: str = ""
    output_filename: str = ""
    last_viewed_record_index: int = 0
    editor_draft_state: dict[str, Any] = Field(default_factory=dict)


class CreateWorkspaceRequest(BaseModel):
    workspace_name: str


class UpdateWorkspaceRequest(BaseModel):
    workspace_name: str | None = None
    loaded_input_datasets: list[LoadedDataset] | None = None
    active_dataset_id: str | None = None
    output_directory: str | None = None
    output_filename: str | None = None
    last_viewed_record_index: int | None = None
    editor_draft_state: dict[str, Any] | None = None


class LoadDatasetRequest(BaseModel):
    workspace_id: str
    path: str


class DatasetRecordResponse(BaseModel):
    dataset_id: str
    index: int
    num_rows: int
    record: dict[str, Any]
    leakage_warnings: list[str] = Field(default_factory=list)


class DatasetRecordsResponse(BaseModel):
    dataset_id: str
    offset: int
    limit: int
    num_rows: int
    records: list[dict[str, Any]]


class JsonlMetaResponse(BaseModel):
    dataset_id: str
    path: str
    format: str = "jsonl"
    num_rows: int
    fields: list[str]
    field_types: dict[str, str] = Field(default_factory=dict)


class JsonlRecordResponse(BaseModel):
    dataset_id: str
    path: str
    index: int
    num_rows: int
    record: dict[str, Any]
    leakage_warnings: list[str] = Field(default_factory=list)


class JsonlRecordsResponse(BaseModel):
    dataset_id: str
    path: str
    offset: int
    limit: int
    num_rows: int
    records: list[dict[str, Any]]


class OutputConfigRequest(BaseModel):
    workspace_id: str | None = None
    output_directory: str
    output_filename: str
    create_dir: bool = False


class OutputConfigResponse(BaseModel):
    output_path: str
    exists: bool
    item_count: int
    last_item_id: str | None = None


class AnswerFormat(BaseModel):
    type: str = ""
    unit: str | None = None
    precision: str | int | float | None = None


class Construct(BaseModel):
    primary: str = ""
    secondary: list[str] = Field(default_factory=list)


class Given(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str = ""
    value: Any = ""


class Variable(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str = ""
    role: str = ""
    domain: str = ""


class Constraint(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = ""
    target: str = ""
    value: Any = ""


class SolutionTraceStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    step_id: int
    premise: str = ""
    operation: str = ""
    expr_before: str | None = None
    expr_after: str | None = None
    verifier_hint: str | None = None


class ValidAnswerSet(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = ""
    value: Any = ""
    tolerance: float | str | None = None


class CounterfactualTransform(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = ""
    description: str = ""
    answer_mapping: str = ""


class LeakageFlags(BaseModel):
    used_original_distractors: bool = False
    used_human_response_dist: bool = False
    used_seed_candidates: bool = False
    original_options_removed: bool = True


class QualityControl(BaseModel):
    manual_checked: bool = False
    answer_verified: bool = False
    trace_verified: bool = False
    operator_applicability_checked: bool = False
    counterfactual_ready: bool = False
    notes: str = ""


class MechanismReadyItem(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    item_id: str = ""
    source_dataset: str = ""
    source_split: str = ""
    source_family: str = ""
    source_record_id: str = ""
    license_note: str = ""
    subject: Literal["math", "physics"] | str = ""
    domain: str = ""
    curriculum_level: CurriculumLevel | str = ""
    question_clean: str = ""
    question_original_available: bool = False
    modification_level: ModificationLevel | str = ""
    correct_answer: Any = ""
    answer_type: AnswerType | str = ""
    answer_format: AnswerFormat = Field(default_factory=AnswerFormat)
    construct_: Construct = Field(default_factory=Construct, alias="construct")
    givens: list[Given] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    solution_trace: list[SolutionTraceStep] = Field(default_factory=list)
    valid_answer_set: ValidAnswerSet = Field(default_factory=ValidAnswerSet)
    allowed_operator_ids: list[str] = Field(default_factory=list)
    operator_precondition_notes: dict[str, str] = Field(default_factory=dict)
    counterfactual_transforms: list[CounterfactualTransform] = Field(default_factory=list)
    leakage_flags: LeakageFlags = Field(default_factory=LeakageFlags)
    quality_control: QualityControl = Field(default_factory=QualityControl)


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    path: str
    message: str


class ValidationResponse(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)


class ValidateOutputRequest(BaseModel):
    item: dict[str, Any]
    output_path: str | None = None


class AppendOutputRequest(BaseModel):
    workspace_id: str | None = None
    item: dict[str, Any]
    output_path: str
    source_dataset_id: str | None = None
    source_record_index: int | None = None


class AppendOutputResponse(BaseModel):
    appended_item_id: str
    output_path: str
    item_count: int


class DraftRequest(BaseModel):
    workspace_id: str
    dataset_id: str
    record_index: int
    item: dict[str, Any] = Field(default_factory=dict)


class DraftLocator(BaseModel):
    workspace_id: str
    dataset_id: str
    record_index: int


class TranslateFieldRequest(BaseModel):
    dataset_id: str
    record_index: int
    field_name: str
    text: str
    record_context: dict[str, Any] = Field(default_factory=dict)


class TranslateFieldResponse(BaseModel):
    dataset_id: str
    record_index: int
    field_name: str
    translation_zh: str
    cached: bool = False


class SourceMetadataTranslationRequest(BaseModel):
    source_metadata_zh: dict[str, str] = Field(default_factory=dict)
    current_english: dict[str, str] = Field(default_factory=dict)
    raw_record: dict[str, Any] = Field(default_factory=dict)


class SourceMetadataTranslationResponse(BaseModel):
    fields: dict[str, str]
    cached: bool = False


class GenerateDraftRequest(BaseModel):
    raw_record: dict[str, Any] = Field(default_factory=dict)
    dataset: dict[str, Any] = Field(default_factory=dict)
    current_item: dict[str, Any] = Field(default_factory=dict)
    problem_translation_zh: str = ""


class GenerateDraftResponse(BaseModel):
    item: dict[str, Any]
