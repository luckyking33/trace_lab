from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx


class DeepSeekError(RuntimeError):
    pass


def load_deepseek_config(repo_root: Path) -> dict[str, str]:
    env_path = repo_root / "apps" / "data_curation_ui" / ".env.local"
    if not env_path.exists():
        raise DeepSeekError("Missing apps/data_curation_ui/.env.local")

    config: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip().strip('"').strip("'")

    api_key = config.get("DEEPSEEK_API_KEY")
    base_url = config.get("base_url")
    model = config.get("model")
    if not api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY is missing in .env.local")
    if not base_url:
        raise DeepSeekError("base_url is missing in .env.local")
    if not model:
        raise DeepSeekError("model is missing in .env.local")
    return config


def call_deepseek(repo_root: Path, messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
    config = load_deepseek_config(repo_root)
    endpoint = chat_completions_endpoint(config["base_url"])
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {config['DEEPSEEK_API_KEY']}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek request failed: {exc}") from exc

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError("DeepSeek response did not contain choices[0].message.content") from exc


def chat_completions_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/chat/completions"


def parse_json_object(text: str) -> dict[str, Any]:
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
    if start == -1 or end == -1 or end <= start:
        raise DeepSeekError("DeepSeek response did not include a JSON object")
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DeepSeekError(f"DeepSeek response JSON could not be parsed: {exc}") from exc

