from pathlib import Path
import csv
import json

from verbatim.experiments.run_conversations import REQUIRED_RUN_FIELDS


def test_artifacts_exist_if_docs_reference_them():
    content = Path("docs/case-study.md").read_text(encoding="utf-8")
    if "artifacts/summary.csv" not in content:
        return

    path = Path("artifacts/summary.csv")
    assert path.exists()

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
    header_lower = [col.strip().lower() for col in header]

    assert "condition" in header_lower
    assert "model" in header_lower
    assert "n" in header_lower
    assert any(name in header_lower for name in ["mean_tokens_per_turn", "mean_tokens", "mean_tokens_turn"])
    assert any(name in header_lower for name in ["drift_slope", "slope"])
    assert any(name in header_lower for name in ["growth_ratio", "growth"])
    assert any(name in header_lower for name in ["pass_rate", "pass"])


def test_backend_venv_not_present_and_ignored():
    assert not Path("backend/venv").exists()
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "backend/venv/" in gitignore


def test_committed_artifacts_are_real_completed_runs():
    for path in Path("artifacts").glob("*/aggregate_metrics.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("status") == "completed", path
        assert payload.get("model") not in (None, "", "mock-echo"), path


# Artifacts written before schema version 2 predate backend/temperature/error fields.
LEGACY_REQUIRED_FIELDS = ("run_id", "model", "intent_id", "condition", "timestamp", "status")


def test_committed_artifacts_have_run_metadata():
    for path in Path("artifacts").glob("*/aggregate_metrics.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("artifact_schema_version", 1) < 2:
            for field in LEGACY_REQUIRED_FIELDS:
                assert payload.get(field) is not None, (path, field)
            continue
        for field in REQUIRED_RUN_FIELDS:
            assert field in payload, (path, field)
            if field == "error" or (field == "token_budget" and payload["condition"] != "budgeted"):
                continue
            assert payload[field] is not None, (path, field)
