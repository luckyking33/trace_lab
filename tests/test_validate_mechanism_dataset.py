from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/validate_mechanism_dataset.py")
CONFIG = Path("configs/mechanism_only.yaml")


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        text=True,
        capture_output=True,
    )


def test_cli_missing_data_file(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    result = run_cli("--input", str(tmp_path / "missing.jsonl"), "--config", str(CONFIG), "--out", str(out))
    assert result.returncode == 1
    assert "Data file not found. Manual data preparation is required." in result.stderr
    assert not out.exists()


def test_cli_success_report(tmp_path: Path, payload_factory) -> None:
    data = tmp_path / "items.jsonl"
    out = tmp_path / "report.json"
    payload = payload_factory()
    data.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = run_cli("--input", str(data), "--config", str(CONFIG), "--out", str(out))
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["n_items"] == 1
    assert report["schema_pass"] == 1
    assert report["leakage_pass"] == 1
    assert report["failed_items"] == []
    assert report["operator_coverage"]["ALG_SIGN_MOVE"] == 1


def test_cli_leakage_failure_report(tmp_path: Path, payload_factory) -> None:
    data = tmp_path / "items.jsonl"
    out = tmp_path / "report.json"
    payload = payload_factory()
    payload["question"] = "CANARY_DO_NOT_USE must not appear."
    data.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = run_cli("--input", str(data), "--config", str(CONFIG), "--out", str(out))
    assert result.returncode == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["failed_items"][0]["stage"] == "leakage"
