from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parents[2]
sys.path.insert(0, str(BACKEND_DIR))

from dataset_loader import DatasetRegistry  # noqa: E402
from jsonl_loader import JsonlLoader, JsonlLoadError  # noqa: E402
from jsonl_writer import JsonlWriter, JsonlWriterError  # noqa: E402
from leakage_guard import PROMPT_FORBIDDEN_KEYS, load_forbidden_keys  # noqa: E402
from path_security import PathSecurityError, resolve_under_repo  # noqa: E402
from validator import OutputValidator  # noqa: E402


def valid_item(item_id: str = "MATH_ALG_001") -> dict:
    return {
        "item_id": item_id,
        "source_dataset": "MATH",
        "source_split": "train",
        "source_family": "competition_math/algebra",
        "source_record_id": "ds_test_0",
        "license_note": "for research use; original options absent",
        "subject": "math",
        "domain": "algebra",
        "curriculum_level": "high_school",
        "question_clean": "Solve for x: 3x - 5 = 16.",
        "question_original_available": False,
        "modification_level": "original_clean",
        "correct_answer": "7",
        "answer_type": "numeric",
        "answer_format": {"type": "integer", "unit": None, "precision": None},
        "construct": {
            "primary": "linear equation solving",
            "secondary": ["inverse operations", "algebraic manipulation"],
        },
        "givens": [{"symbol": "equation", "value": "3*x - 5 = 16"}],
        "variables": [{"symbol": "x", "role": "unknown", "domain": "real"}],
        "constraints": [{"type": "domain", "target": "x", "value": "real"}],
        "solution_trace": [
            {
                "step_id": 1,
                "premise": "given equation",
                "operation": "read equation",
                "expr_before": None,
                "expr_after": "3*x - 5 = 16",
                "verifier_hint": "sympy_equation",
            },
            {
                "step_id": 2,
                "premise": "subtract constant",
                "operation": "add 5 to both sides",
                "expr_before": "3*x - 5 = 16",
                "expr_after": "3*x = 21",
                "verifier_hint": "sympy_equation",
            },
            {
                "step_id": 3,
                "premise": "divide coefficient",
                "operation": "divide both sides by 3",
                "expr_before": "3*x = 21",
                "expr_after": "x = 7",
                "verifier_hint": "sympy_equation",
            },
        ],
        "valid_answer_set": {"type": "sympy_equiv", "value": "7", "tolerance": None},
        "allowed_operator_ids": ["ALG_SIGN_MOVE", "ALG_DIVISION_ERROR", "ALG_CONSTANT_MOVE"],
        "operator_precondition_notes": {
            "ALG_SIGN_MOVE": "linear equation contains constant term moved across equality"
        },
        "counterfactual_transforms": [
            {"type": "variable_renaming", "description": "replace x with y", "answer_mapping": "identity"},
            {"type": "numeric_perturbation", "description": "change constants", "answer_mapping": "recompute"},
            {"type": "paraphrase", "description": "rewrite without changing equation", "answer_mapping": "identity"},
        ],
        "leakage_flags": {
            "used_original_distractors": False,
            "used_human_response_dist": False,
            "used_seed_candidates": False,
            "original_options_removed": True,
        },
        "quality_control": {
            "manual_checked": True,
            "answer_verified": True,
            "trace_verified": True,
            "operator_applicability_checked": True,
            "counterfactual_ready": True,
            "notes": "",
        },
    }


def test_load_arrow_file_path_missing_clear_error() -> None:
    registry = DatasetRegistry(REPO_ROOT, load_forbidden_keys(REPO_ROOT))
    with pytest.raises(PathSecurityError, match="Path does not exist"):
        registry.load("data/competition_math/train/missing.arrow")


def test_load_dataset_meta_from_competition_math_arrow() -> None:
    arrow = REPO_ROOT / "data" / "competition_math" / "train" / "data-00000-of-00001.arrow"
    if not arrow.exists():
        pytest.skip("competition_math arrow file is not present")
    registry = DatasetRegistry(REPO_ROOT, load_forbidden_keys(REPO_ROOT))
    ref = registry.load("data/competition_math/train/data-00000-of-00001.arrow")
    meta = registry.meta(ref.dataset_id)
    assert meta.num_rows == 12500
    assert meta.fields == ["problem", "level", "type", "solution"]


def test_get_record_by_index_from_competition_math_arrow() -> None:
    arrow = REPO_ROOT / "data" / "competition_math" / "train" / "data-00000-of-00001.arrow"
    if not arrow.exists():
        pytest.skip("competition_math arrow file is not present")
    registry = DatasetRegistry(REPO_ROOT, load_forbidden_keys(REPO_ROOT))
    ref = registry.load("data/competition_math/train/data-00000-of-00001.arrow")
    record = registry.record(ref.dataset_id, 0)
    assert record.index == 0
    assert {"problem", "solution", "level", "type"} <= set(record.record)
    assert record.num_rows == 12500


def test_validate_valid_item(tmp_path: Path) -> None:
    validator = OutputValidator(tmp_path, PROMPT_FORBIDDEN_KEYS)
    out_dir = tmp_path / "data" / "derived_no_options"
    out_dir.mkdir(parents=True)
    response = validator.validate(valid_item(), "data/derived_no_options/items.jsonl")
    assert response.valid is True
    assert response.errors == []


def test_reject_missing_required_fields(tmp_path: Path) -> None:
    validator = OutputValidator(tmp_path, PROMPT_FORBIDDEN_KEYS)
    item = valid_item()
    item.pop("question_clean")
    response = validator.validate(item)
    assert response.valid is False
    assert any(error.path == "question_clean" for error in response.errors)


def test_reject_forbidden_leakage_keys(tmp_path: Path) -> None:
    validator = OutputValidator(tmp_path, PROMPT_FORBIDDEN_KEYS)
    item = valid_item()
    item["metadata"] = {"choices": ["unsafe"]}
    response = validator.validate(item)
    assert response.valid is False
    assert any(error.path == "leakage" for error in response.errors)


def test_reject_duplicate_item_id(tmp_path: Path) -> None:
    out_dir = tmp_path / "data" / "derived_no_options"
    out_dir.mkdir(parents=True)
    output_path = out_dir / "items.jsonl"
    output_path.write_text(json.dumps({"item_id": "MATH_ALG_001"}) + "\n", encoding="utf-8")
    writer = JsonlWriter(tmp_path)
    with pytest.raises(JsonlWriterError, match="Duplicate item_id"):
        writer.append(
            "data/derived_no_options/items.jsonl",
            valid_item(),
            workspace_id="ws_test",
            source_dataset_id="ds_test",
            source_record_index=0,
        )


def test_reject_output_path_in_source_quarantine(tmp_path: Path) -> None:
    quarantine = tmp_path / "data" / "source_quarantine"
    quarantine.mkdir(parents=True)
    with pytest.raises(PathSecurityError, match="source_quarantine"):
        resolve_under_repo("data/source_quarantine/items.jsonl", tmp_path)


def test_append_valid_item_to_jsonl_and_log(tmp_path: Path) -> None:
    out_dir = tmp_path / "data" / "derived_no_options"
    out_dir.mkdir(parents=True)
    writer = JsonlWriter(tmp_path)
    count = writer.append(
        "data/derived_no_options/items.jsonl",
        valid_item(),
        workspace_id="ws_test",
        source_dataset_id="ds_test",
        source_record_index=3,
    )
    assert count == 1
    output_path = out_dir / "items.jsonl"
    assert json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])["item_id"] == "MATH_ALG_001"
    log_path = tmp_path / ".dg_curation" / "append_log.jsonl"
    assert "MATH_ALG_001" in log_path.read_text(encoding="utf-8")


def test_jsonl_loader_meta_record_and_pagination(tmp_path: Path) -> None:
    out_dir = tmp_path / "data" / "derived_no_options"
    out_dir.mkdir(parents=True)
    output_path = out_dir / "items.jsonl"
    rows = [valid_item("MATH_ALG_001"), valid_item("MATH_ALG_002")]
    output_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    loader = JsonlLoader(tmp_path, PROMPT_FORBIDDEN_KEYS)
    meta = loader.meta("data/derived_no_options/items.jsonl")
    assert meta["format"] == "jsonl"
    assert meta["num_rows"] == 2
    assert "question_clean" in meta["fields"]

    record = loader.record("data/derived_no_options/items.jsonl", 1)
    assert record["record"]["item_id"] == "MATH_ALG_002"

    page = loader.records("data/derived_no_options/items.jsonl", offset=0, limit=1)
    assert page["num_rows"] == 2
    assert len(page["records"]) == 1


def test_jsonl_loader_rejects_invalid_jsonl(tmp_path: Path) -> None:
    out_dir = tmp_path / "data" / "derived_no_options"
    out_dir.mkdir(parents=True)
    (out_dir / "items.jsonl").write_text('{"item_id": "ok"}\nnot-json\n', encoding="utf-8")

    loader = JsonlLoader(tmp_path, PROMPT_FORBIDDEN_KEYS)
    with pytest.raises(JsonlLoadError, match="Invalid JSONL at line 2"):
        loader.meta("data/derived_no_options/items.jsonl")
