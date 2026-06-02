from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


SCRIPT_PATH = Path("scripts/generate_math_cei_pairs_with_llm.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location("generate_math_cei_pairs_with_llm", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _source_record() -> dict[str, Any]:
    return {
        "item_id": "MATH_SRC_001",
        "item_role": "operator_unit_positive",
        "source": "manual",
        "subject": "math",
        "domain": "algebra",
        "question": "Solve for x: 3*x - 5 = 16.",
        "correct_answer": {"type": "numeric", "value": "7"},
        "answer_type": "numeric",
        "givens": [{"symbol": "equation", "value": "3*x - 5 = 16"}],
        "constraints": [{"var": "x", "domain": "real"}],
        "solution_trace": [
            {"step_id": 1, "expr": "3*x - 5 = 16", "operation": "given", "metadata": {}},
            {
                "step_id": 2,
                "expr": "x = 7",
                "operation": "solve",
                "result": "7",
                "metadata": {"derived_answer": "7"},
            },
        ],
        "allowed_operator_ids": ["ALG_SIGN_MOVE"],
        "target_error_operator_id": "ALG_SIGN_MOVE",
        "distractor_answer": {"type": "numeric", "value": "11/3"},
        "wrong_solution_trace": [
            {"step_id": 1, "expr": "3*x - 5 = 16", "operation": "given", "metadata": {}},
            {
                "step_id": 2,
                "expr": "3*x = 16 - 5",
                "operation": "move -5 without changing sign",
                "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
            },
            {
                "step_id": 3,
                "expr": "x = 11/3",
                "operation": "divide by 3",
                "result": "11/3",
                "metadata": {"derived_answer": "11/3"},
            },
        ],
        "counterfactual_transforms": ["variable_renaming"],
        "leakage_flags": {
            "original_distractors_removed": True,
            "human_response_dist_removed": True,
            "seed_candidates_removed": True,
        },
    }


def _valid_pair() -> dict[str, Any]:
    return {
        "cei_pair_id": "CEI_MATH_SRC_001_VAR_RENAME",
        "source_item_id": "MATH_SRC_001",
        "source_certificate_id": "MATH_SRC_001::certificate_1",
        "operator_id": "ALG_SIGN_MOVE",
        "transform_type": "variable_renaming",
        "source_wrong_answer": {"type": "numeric", "value": "11/3"},
        "transformed_item": {
            "item_id": "MATH_SRC_001_VAR",
            "subject": "math",
            "domain": "algebra",
            "question_clean": "Solve for y: 3*y - 5 = 16.",
            "correct_answer": {"type": "numeric", "value": "7"},
            "answer_type": "numeric",
            "givens": [{"symbol": "equation", "value": "3*y - 5 = 16"}],
            "solution_trace": [
                {"step_id": 1, "expr": "3*y - 5 = 16", "operation": "given", "metadata": {}},
                {
                    "step_id": 2,
                    "expr": "y = 7",
                    "operation": "solve",
                    "result": "7",
                    "metadata": {"derived_answer": "7"},
                },
            ],
        },
        "transformed_certificate": {
            "candidate_answer": {"type": "numeric", "value": "11/3"},
            "wrong_solution_trace": [
                {"step_id": 1, "expr": "3*y - 5 = 16", "operation": "given", "metadata": {}},
                {
                    "step_id": 2,
                    "expr": "3*y = 16 - 5",
                    "operation": "move -5 without changing sign",
                    "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
                },
                {
                    "step_id": 3,
                    "expr": "y = 11/3",
                    "operation": "divide by 3",
                    "result": "11/3",
                    "metadata": {"derived_answer": "11/3"},
                },
            ],
            "applied_operator_ids": ["ALG_SIGN_MOVE"],
        },
        "answer_mapping": {"type": "identity"},
    }


def _invalid_pair() -> dict[str, Any]:
    pair = _valid_pair()
    pair["transformed_certificate"]["candidate_answer"] = {"type": "numeric", "value": "4"}
    pair["transformed_certificate"]["wrong_solution_trace"][-1]["result"] = "4"
    pair["transformed_certificate"]["wrong_solution_trace"][-1]["metadata"]["derived_answer"] = "4"
    return pair


def _write_fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    data_path = tmp_path / "items.jsonl"
    data_path.write_text(json.dumps(_source_record()) + "\n", encoding="utf-8")

    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    with (audit_dir / "certificate_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["item_id", "certificate_id", "applied_operator_ids", "is_composite", "validation_status", "mev_v1"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "item_id": "MATH_SRC_001",
                "certificate_id": "MATH_SRC_001::certificate_1",
                "applied_operator_ids": json.dumps(["ALG_SIGN_MOVE"]),
                "is_composite": "false",
                "validation_status": "validated",
                "mev_v1": "1.0",
            }
        )
        writer.writerow(
            {
                "item_id": "MATH_SRC_001",
                "certificate_id": "SKIP_COMPOSITE",
                "applied_operator_ids": json.dumps(["ALG_SIGN_MOVE", "ALG_DISTRIBUTIVE_DROP"]),
                "is_composite": "true",
                "validation_status": "validated",
                "mev_v1": "1.0",
            }
        )
        writer.writerow(
            {
                "item_id": "MATH_SRC_001",
                "certificate_id": "SKIP_FAILED",
                "applied_operator_ids": json.dumps(["ALG_SIGN_MOVE"]),
                "is_composite": "false",
                "validation_status": "failed",
                "mev_v1": "0.0",
            }
        )
    return data_path, audit_dir


def test_select_source_certificates_filters_to_validated_single_operator(tmp_path: Path) -> None:
    module = _load_script_module()
    data_path, audit_dir = _write_fixture_files(tmp_path)

    selected = module.select_source_certificates(data_path, audit_dir, max_per_operator=2)

    assert len(selected) == 1
    assert selected[0]["source_certificate_id"] == "MATH_SRC_001::certificate_1"
    assert selected[0]["operator_id"] == "ALG_SIGN_MOVE"


def test_generation_prompt_contains_few_shot_and_required_schema(tmp_path: Path) -> None:
    module = _load_script_module()
    data_path, audit_dir = _write_fixture_files(tmp_path)
    source = module.select_source_certificates(data_path, audit_dir, max_per_operator=1)[0]

    messages = module.build_generation_prompt(source_bundle=source, transform_type="variable_renaming")
    prompt_text = messages[-1]["content"]

    assert "few_shot_examples" in prompt_text
    assert "numeric_perturbation_explicit_expected" in prompt_text
    assert "required_output_schema" in prompt_text
    assert "transformed_certificate" in prompt_text
    assert "answer_mapping" in prompt_text


def test_valid_fake_response_is_written_to_generated_jsonl(tmp_path: Path) -> None:
    module = _load_script_module()
    data_path, audit_dir = _write_fixture_files(tmp_path)
    output = tmp_path / "math_cei_pairs.generated.jsonl"
    generation_dir = tmp_path / "generation"

    def fake_chat(_messages):
        return json.dumps(_valid_pair())

    summary = module.generate_cei_pairs(
        input_data=data_path,
        audit_dir=audit_dir,
        output=output,
        generation_dir=generation_dir,
        max_per_operator=1,
        transforms=["variable_renaming"],
        retries=0,
        chat_func=fake_chat,
    )

    assert summary["accepted_pairs"] == 1
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["cei_pair_id"] == "CEI_MATH_SRC_001_VAR_RENAME"
    assert (generation_dir / "generation_audit.csv").exists()
    assert (generation_dir / "raw_responses.jsonl").exists()


def test_invalid_response_triggers_repair_retry(tmp_path: Path) -> None:
    module = _load_script_module()
    data_path, audit_dir = _write_fixture_files(tmp_path)
    output = tmp_path / "math_cei_pairs.generated.jsonl"
    generation_dir = tmp_path / "generation"
    responses = [json.dumps(_invalid_pair()), json.dumps(_valid_pair())]

    def fake_chat(_messages):
        return responses.pop(0)

    summary = module.generate_cei_pairs(
        input_data=data_path,
        audit_dir=audit_dir,
        output=output,
        generation_dir=generation_dir,
        max_per_operator=1,
        transforms=["variable_renaming"],
        retries=1,
        chat_func=fake_chat,
    )

    assert summary["accepted_pairs"] == 1
    raw_rows = [json.loads(line) for line in (generation_dir / "raw_responses.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["attempt"] for row in raw_rows] == [1, 2]


def test_rejected_response_is_written_to_rejected_jsonl(tmp_path: Path) -> None:
    module = _load_script_module()
    data_path, audit_dir = _write_fixture_files(tmp_path)
    output = tmp_path / "math_cei_pairs.generated.jsonl"
    generation_dir = tmp_path / "generation"

    def fake_chat(_messages):
        return json.dumps(_invalid_pair())

    summary = module.generate_cei_pairs(
        input_data=data_path,
        audit_dir=audit_dir,
        output=output,
        generation_dir=generation_dir,
        max_per_operator=1,
        transforms=["variable_renaming"],
        retries=0,
        chat_func=fake_chat,
    )

    assert summary["accepted_pairs"] == 0
    assert summary["rejected_pairs"] == 1
    rejected = [json.loads(line) for line in (generation_dir / "rejected.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rejected[0]["source_certificate_id"] == "MATH_SRC_001::certificate_1"
    assert output.read_text(encoding="utf-8") == ""


def test_missing_env_fields_fail_without_printing_secret(tmp_path: Path) -> None:
    module = _load_script_module()
    env_dir = tmp_path / "apps" / "data_curation_ui"
    env_dir.mkdir(parents=True)
    (env_dir / ".env.local").write_text(
        "DEEPSEEK_API_KEY=SECRET_SHOULD_NOT_APPEAR\nbase_url=https://example.test/v1\n",
        encoding="utf-8",
    )

    with pytest.raises(module.LLMGenerationError) as exc_info:
        module.load_env_config(tmp_path)

    error_text = str(exc_info.value)
    assert "model" in error_text
    assert "SECRET_SHOULD_NOT_APPEAR" not in error_text
