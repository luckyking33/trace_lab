#!/usr/bin/env python3
"""Generate draft math CEI pairs with an OpenAI-compatible LLM API."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from respondent_lab.certificates.extraction import extract_certificates  # noqa: E402
from respondent_lab.counterfactual.cei_pairs import validate_cei_pair  # noqa: E402
from respondent_lab.io.math_dataset_loader import load_and_normalize_math_items  # noqa: E402


REQUIRED_ENV_KEYS = ["DEEPSEEK_API_KEY", "base_url", "model"]
GENERATION_AUDIT_COLUMNS = [
    "cei_pair_id",
    "source_item_id",
    "source_certificate_id",
    "operator_id",
    "transform_type",
    "attempts",
    "accepted",
    "answer_mapping_type",
    "transformed_certificate_mev_v1",
    "cei_pair_pass",
    "notes",
]


class LLMGenerationError(RuntimeError):
    """Raised when generation setup or API calls fail."""


def _json_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GENERATION_AUDIT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_cell(row.get(key)) for key in GENERATION_AUDIT_COLUMNS})


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            json.dump(row, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")


def _parse_json_cell(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _bool_cell(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def _float_cell(value: str | None) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _chat_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/chat/completions"


def load_env_config(repo_root: Path = ROOT) -> dict[str, str]:
    """Load API configuration without exposing secret values."""

    env_path = repo_root / "apps" / "data_curation_ui" / ".env.local"
    if not env_path.exists():
        raise LLMGenerationError("Missing apps/data_curation_ui/.env.local")

    config: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip().strip('"').strip("'")

    missing = [key for key in REQUIRED_ENV_KEYS if not config.get(key)]
    if missing:
        raise LLMGenerationError(f"Missing required API config keys: {', '.join(missing)}")
    return config


def chat_completion(
    messages: list[dict[str, str]],
    *,
    repo_root: Path = ROOT,
    temperature: float = 0.1,
    timeout_seconds: int = 90,
) -> str:
    """Call an OpenAI-compatible chat completions endpoint using stdlib HTTP."""

    config = load_env_config(repo_root)
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    request = urllib.request.Request(
        _chat_endpoint(config["base_url"]),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['DEEPSEEK_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise LLMGenerationError(f"LLM request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LLMGenerationError(f"LLM request failed: {exc.reason}") from exc

    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMGenerationError("LLM response missing choices[0].message.content") from exc


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract a single JSON object from a model response."""

    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise LLMGenerationError("LLM response did not contain a JSON object")
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMGenerationError(f"LLM response JSON parse failed: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMGenerationError("LLM response JSON root must be an object")
    return parsed


def _load_source_lookup(audit_dir: Path) -> dict[str, dict[str, Any]]:
    audit_csv = audit_dir / "certificate_audit.csv"
    if not audit_csv.exists():
        raise FileNotFoundError(f"certificate audit CSV not found: {audit_csv}")
    with audit_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {str(row.get("certificate_id") or ""): row for row in rows if row.get("certificate_id")}


def _certificate_operator_id(row: dict[str, str]) -> str:
    operator_ids = _parse_json_cell(row.get("applied_operator_ids"))
    if isinstance(operator_ids, list) and len(operator_ids) == 1:
        return str(operator_ids[0])
    return ""


def _certificate_lookup(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for record in records:
        for certificate in extract_certificates(record):
            cert_id = str(certificate.get("certificate_id") or "")
            if cert_id:
                lookup[cert_id] = certificate
    return lookup


def select_source_certificates(
    input_data: Path,
    audit_dir: Path,
    *,
    max_per_operator: int = 2,
) -> list[dict[str, Any]]:
    """Select validated single-operator source certificates for LLM generation."""

    records = load_and_normalize_math_items(input_data)
    record_lookup = {str(record.get("item_id") or ""): record for record in records}
    cert_lookup = _certificate_lookup(records)
    audit_csv = audit_dir / "certificate_audit.csv"
    if not audit_csv.exists():
        raise FileNotFoundError(f"certificate audit CSV not found: {audit_csv}")

    with audit_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    selected_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    for row in rows:
        if row.get("validation_status") != "validated":
            continue
        if _bool_cell(row.get("is_composite")):
            continue
        if _float_cell(row.get("mev_v1")) != 1.0:
            continue
        operator_id = _certificate_operator_id(row)
        if not operator_id or selected_counts[operator_id] >= max_per_operator:
            continue

        item_id = str(row.get("item_id") or "")
        certificate_id = str(row.get("certificate_id") or "")
        record = record_lookup.get(item_id)
        certificate = cert_lookup.get(certificate_id)
        if record is None or certificate is None:
            continue

        selected_counts[operator_id] += 1
        selected.append(
            {
                "source_item": record,
                "source_certificate": certificate,
                "source_audit_row": row,
                "operator_id": operator_id,
                "source_item_id": item_id,
                "source_certificate_id": certificate_id,
            }
        )
    return selected


FEW_SHOT_EXAMPLES = [
    {
        "case": "variable_renaming_numeric_identity",
        "input_summary": {
            "source_item_id": "MATH_ALG_SIGN_001",
            "operator_id": "ALG_SIGN_MOVE",
            "transform_type": "variable_renaming",
            "source_wrong_answer": {"type": "numeric", "value": "19/2"},
        },
        "output": {
            "cei_pair_id": "CEI_MATH_ALG_SIGN_001_VAR_RENAME",
            "source_item_id": "MATH_ALG_SIGN_001",
            "source_certificate_id": "MATH_ALG_SIGN_001::certificate_1",
            "operator_id": "ALG_SIGN_MOVE",
            "transform_type": "variable_renaming",
            "source_wrong_answer": {"type": "numeric", "value": "19/2"},
            "transformed_item": {
                "item_id": "MATH_ALG_SIGN_001_VAR",
                "subject": "math",
                "domain": "algebra",
                "question_clean": "Solve for y: 4y + 7 = 31.",
                "correct_answer": {"type": "numeric", "value": "6"},
                "answer_type": "numeric",
                "givens": [{"symbol": "equation", "value": "4*y + 7 = 31"}],
                "constraints": [{"var": "y", "domain": "real"}],
                "solution_trace": [
                    {"step_id": 1, "expr": "4*y + 7 = 31", "operation": "given", "metadata": {}},
                    {"step_id": 2, "expr": "4*y = 24", "operation": "subtract 7 from both sides", "metadata": {}},
                    {
                        "step_id": 3,
                        "expr": "y = 6",
                        "operation": "divide both sides by 4",
                        "result": "6",
                        "metadata": {"derived_answer": "6"},
                    },
                ],
                "allowed_operator_ids": ["ALG_SIGN_MOVE"],
            },
            "transformed_certificate": {
                "applied_operator_ids": ["ALG_SIGN_MOVE"],
                "candidate_answer": {"type": "numeric", "value": "19/2"},
                "wrong_solution_trace": [
                    {"step_id": 1, "expr": "4*y + 7 = 31", "operation": "given", "metadata": {}},
                    {
                        "step_id": 2,
                        "expr": "4*y = 31 + 7",
                        "operation": "move +7 to right side but keep its sign",
                        "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
                    },
                    {"step_id": 3, "expr": "4*y = 38", "operation": "simplify", "metadata": {}},
                    {
                        "step_id": 4,
                        "expr": "y = 19/2",
                        "operation": "divide both sides by 4",
                        "result": "19/2",
                        "metadata": {"derived_answer": "19/2"},
                    },
                ],
            },
            "answer_mapping": {"type": "identity"},
        },
    },
    {
        "case": "numeric_perturbation_explicit_expected",
        "input_summary": {
            "source_item_id": "MATH_ALG_SIGN_001",
            "operator_id": "ALG_SIGN_MOVE",
            "transform_type": "numeric_perturbation",
            "source_wrong_answer": {"type": "numeric", "value": "19/2"},
        },
        "output": {
            "cei_pair_id": "CEI_MATH_ALG_SIGN_001_NUM_PERTURB",
            "source_item_id": "MATH_ALG_SIGN_001",
            "source_certificate_id": "MATH_ALG_SIGN_001::certificate_1",
            "operator_id": "ALG_SIGN_MOVE",
            "transform_type": "numeric_perturbation",
            "source_wrong_answer": {"type": "numeric", "value": "19/2"},
            "transformed_item": {
                "item_id": "MATH_ALG_SIGN_001_NUM",
                "subject": "math",
                "domain": "algebra",
                "question_clean": "Solve for x: 5*x + 6 = 31.",
                "correct_answer": {"type": "numeric", "value": "5"},
                "answer_type": "numeric",
                "givens": [{"symbol": "equation", "value": "5*x + 6 = 31"}],
                "constraints": [{"var": "x", "domain": "real"}],
                "solution_trace": [
                    {"step_id": 1, "expr": "5*x + 6 = 31", "operation": "given", "metadata": {}},
                    {"step_id": 2, "expr": "5*x = 25", "operation": "subtract 6 from both sides", "metadata": {}},
                    {
                        "step_id": 3,
                        "expr": "x = 5",
                        "operation": "divide both sides by 5",
                        "result": "5",
                        "metadata": {"derived_answer": "5"},
                    },
                ],
                "allowed_operator_ids": ["ALG_SIGN_MOVE"],
            },
            "transformed_certificate": {
                "applied_operator_ids": ["ALG_SIGN_MOVE"],
                "candidate_answer": {"type": "numeric", "value": "37/5"},
                "wrong_solution_trace": [
                    {"step_id": 1, "expr": "5*x + 6 = 31", "operation": "given", "metadata": {}},
                    {
                        "step_id": 2,
                        "expr": "5*x = 31 + 6",
                        "operation": "move +6 to right side but keep its sign",
                        "metadata": {"error_operator_id": "ALG_SIGN_MOVE"},
                    },
                    {
                        "step_id": 3,
                        "expr": "x = 37/5",
                        "operation": "divide both sides by 5",
                        "result": "37/5",
                        "metadata": {"derived_answer": "37/5"},
                    },
                ],
            },
            "answer_mapping": {
                "type": "explicit_expected",
                "expected_transformed_wrong_answer": {"type": "numeric", "value": "37/5"},
            },
        },
    },
]


def _source_wrong_answer(source_certificate: dict[str, Any]) -> dict[str, Any]:
    answer = source_certificate.get("candidate_answer")
    if isinstance(answer, dict):
        return answer
    return {"type": "TODO", "value": "TODO"}


def build_generation_prompt(
    *,
    source_bundle: dict[str, Any],
    transform_type: str,
) -> list[dict[str, str]]:
    """Build a few-shot prompt for one CEI pair."""

    operator_id = source_bundle["operator_id"]
    source_item = source_bundle["source_item"]
    source_certificate = source_bundle["source_certificate"]
    source_certificate_id = source_bundle["source_certificate_id"]
    source_wrong_answer = _source_wrong_answer(source_certificate)
    pair_id = f"CEI_{source_certificate_id.replace('::', '_').replace(':', '_')}_{transform_type}".upper()
    output_schema = {
        "cei_pair_id": pair_id,
        "source_item_id": source_bundle["source_item_id"],
        "source_certificate_id": source_certificate_id,
        "operator_id": operator_id,
        "transform_type": transform_type,
        "source_wrong_answer": source_wrong_answer,
        "transformed_item": {
            "item_id": "string",
            "subject": "math",
            "domain": "string",
            "question_clean": "string",
            "correct_answer": {"type": "numeric|formula|answer_set", "value": "string or list"},
            "answer_type": "numeric|formula|answer_set",
            "givens": [{"symbol": "string", "value": "string"}],
            "constraints": [],
            "solution_trace": [
                {"step_id": 1, "expr": "string", "operation": "string", "metadata": {}}
            ],
            "allowed_operator_ids": [operator_id],
        },
        "transformed_certificate": {
            "applied_operator_ids": [operator_id],
            "candidate_answer": {"type": "numeric|formula|answer_set", "value": "string or list"},
            "wrong_solution_trace": [
                {
                    "step_id": 1,
                    "expr": "string",
                    "operation": "string",
                    "metadata": {"error_operator_id": operator_id},
                }
            ],
        },
        "answer_mapping": {"type": "identity|variable_substitution|explicit_expected"},
    }
    task_payload = {
        "requested_pair_id": pair_id,
        "operator_id": operator_id,
        "transform_type": transform_type,
        "source_wrong_answer": source_wrong_answer,
        "source_item": source_item,
        "source_certificate": source_certificate,
        "required_output_schema": output_schema,
        "local_validation_rules": [
            "Return exactly one JSON object and no markdown.",
            "Do not include distractors, original options, student distributions, or seed candidates.",
            "transformed_certificate.applied_operator_ids must equal [operator_id].",
            "wrong_solution_trace must contain exactly one step with metadata.error_operator_id equal to operator_id.",
            "candidate_answer must equal the derived_answer or final result in wrong_solution_trace.",
            "candidate_answer must be incorrect relative to transformed_item.correct_answer.",
            "For variable_renaming, preserve construct and use identity for numeric answers or variable_substitution for symbolic answers.",
            "For numeric_perturbation, choose nearby clean numbers and use explicit_expected mapping.",
        ],
    }
    system = (
        "You are a deterministic math dataset curator for counterfactual error invariance. "
        "Return exactly one JSON object. Do not return markdown, comments, or explanations. "
        "You must preserve the same error mechanism under the requested transform."
    )
    user = {
        "few_shot_examples": FEW_SHOT_EXAMPLES,
        "task": task_payload,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, indent=2, sort_keys=True)},
    ]


def repair_prompt_from_validation_errors(
    *,
    source_bundle: dict[str, Any],
    transform_type: str,
    previous_pair: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    parse_error: str | None = None,
) -> list[dict[str, str]]:
    """Build a repair prompt that includes deterministic validation feedback."""

    messages = build_generation_prompt(source_bundle=source_bundle, transform_type=transform_type)
    repair_payload = {
        "previous_output": previous_pair,
        "parse_error": parse_error,
        "validation_result": validation,
        "repair_instruction": (
            "Repair the JSON object so it passes local CEI validation. Keep the same source ids, "
            "operator_id, and transform_type. Return only the corrected JSON object."
        ),
    }
    messages.append({"role": "user", "content": json.dumps(repair_payload, ensure_ascii=False, indent=2)})
    return messages


def _validate_generated_pair(
    pair: dict[str, Any],
    source_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return validate_cei_pair(pair, source_lookup)


def _audit_row(pair: dict[str, Any] | None, validation: dict[str, Any] | None, attempts: int) -> dict[str, Any]:
    pair = pair or {}
    validation = validation or {}
    return {
        "cei_pair_id": pair.get("cei_pair_id") or validation.get("cei_pair_id") or "",
        "source_item_id": pair.get("source_item_id") or validation.get("source_item_id") or "",
        "source_certificate_id": pair.get("source_certificate_id") or validation.get("source_certificate_id") or "",
        "operator_id": pair.get("operator_id") or validation.get("operator_id") or "",
        "transform_type": pair.get("transform_type") or validation.get("transform_type") or "",
        "attempts": attempts,
        "accepted": bool(validation.get("cei_pair_pass")),
        "answer_mapping_type": validation.get("answer_mapping_type") or "",
        "transformed_certificate_mev_v1": validation.get("transformed_certificate_mev_v1"),
        "cei_pair_pass": bool(validation.get("cei_pair_pass")),
        "notes": validation.get("notes") or [],
    }


def generate_cei_pairs(
    *,
    input_data: Path,
    audit_dir: Path,
    output: Path,
    generation_dir: Path,
    max_per_operator: int,
    transforms: list[str],
    retries: int,
    chat_func: Callable[[list[dict[str, str]]], str] | None = None,
    sleep_seconds: float = 0.0,
) -> dict[str, Any]:
    """Generate and validate CEI pairs, writing only locally accepted pairs."""

    chat_func = chat_func or (lambda messages: chat_completion(messages))
    source_lookup = _load_source_lookup(audit_dir)
    sources = select_source_certificates(input_data, audit_dir, max_per_operator=max_per_operator)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    raw_responses: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    for source in sources:
        for transform_type in transforms:
            previous_pair: dict[str, Any] | None = None
            validation: dict[str, Any] | None = None
            parse_error: str | None = None
            accepted_pair: dict[str, Any] | None = None

            for attempt in range(1, retries + 2):
                if attempt == 1:
                    messages = build_generation_prompt(source_bundle=source, transform_type=transform_type)
                else:
                    messages = repair_prompt_from_validation_errors(
                        source_bundle=source,
                        transform_type=transform_type,
                        previous_pair=previous_pair,
                        validation=validation,
                        parse_error=parse_error,
                    )
                raw_text = chat_func(messages)
                raw_responses.append(
                    {
                        "source_certificate_id": source["source_certificate_id"],
                        "operator_id": source["operator_id"],
                        "transform_type": transform_type,
                        "attempt": attempt,
                        "response": raw_text,
                    }
                )
                parse_error = None
                try:
                    pair = parse_json_object(raw_text)
                    previous_pair = pair
                    validation = _validate_generated_pair(pair, source_lookup)
                except Exception as exc:  # noqa: BLE001 - record parse/validation failures.
                    pair = None
                    validation = None
                    parse_error = str(exc)

                if validation and validation.get("cei_pair_pass"):
                    accepted_pair = previous_pair
                    audit_rows.append(_audit_row(accepted_pair, validation, attempt))
                    break
                if sleep_seconds:
                    time.sleep(sleep_seconds)

            if accepted_pair is not None:
                accepted.append(accepted_pair)
            else:
                rejected.append(
                    {
                        "source_item_id": source["source_item_id"],
                        "source_certificate_id": source["source_certificate_id"],
                        "operator_id": source["operator_id"],
                        "transform_type": transform_type,
                        "last_pair": previous_pair,
                        "last_validation": validation,
                        "parse_error": parse_error,
                    }
                )
                audit_rows.append(_audit_row(previous_pair, validation, retries + 1))

    _write_jsonl(output, accepted)
    _write_csv(generation_dir / "generation_audit.csv", audit_rows)
    _write_jsonl(generation_dir / "rejected.jsonl", rejected)
    _write_jsonl(generation_dir / "raw_responses.jsonl", raw_responses)

    return {
        "selected_source_certificates": len(sources),
        "requested_pairs": len(sources) * len(transforms),
        "accepted_pairs": len(accepted),
        "rejected_pairs": len(rejected),
        "output": str(output),
        "generation_dir": str(generation_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-data", required=True, type=Path)
    parser.add_argument("--audit-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--generation-dir", required=True, type=Path)
    parser.add_argument("--max-per-operator", type=int, default=2)
    parser.add_argument("--transforms", default="variable_renaming,numeric_perturbation")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    args = parser.parse_args()

    transforms = [item.strip() for item in args.transforms.split(",") if item.strip()]
    try:
        summary = generate_cei_pairs(
            input_data=args.input_data,
            audit_dir=args.audit_dir,
            output=args.output,
            generation_dir=args.generation_dir,
            max_per_operator=args.max_per_operator,
            transforms=transforms,
            retries=args.retries,
            sleep_seconds=args.sleep_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should fail clearly without secrets.
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
