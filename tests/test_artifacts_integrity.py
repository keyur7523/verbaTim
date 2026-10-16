from collections import Counter
from pathlib import Path
import csv
import json

import pytest

from verbatim.analysis.contamination import run_dir_mock_reasons
from verbatim.experiments.run_conversations import REQUIRED_RUN_FIELDS

# Every directory of committed run artifacts.
COMMITTED_RUN_DIRS = ["artifacts", "artifacts_rerun"]


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
    assert "length_unit" in header_lower
    assert any(name in header_lower for name in ["mean_tokens_per_turn", "mean_tokens", "mean_tokens_turn"])
    assert any(name in header_lower for name in ["drift_slope", "slope"])
    assert any(name in header_lower for name in ["growth_ratio", "growth"])
    assert any(name in header_lower for name in ["pass_rate", "pass"])


def test_backend_venv_not_present_and_ignored():
    assert not Path("backend/venv").exists()
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "backend/venv/" in gitignore


@pytest.mark.parametrize("root", COMMITTED_RUN_DIRS)
def test_committed_artifacts_are_real_completed_runs(root):
    for path in Path(root).glob("*/aggregate_metrics.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("status") == "completed", path
        assert payload.get("model") not in (None, "", "mock-echo"), path
        assert payload.get("backend") != "mock", path


@pytest.mark.parametrize("root", COMMITTED_RUN_DIRS)
def test_committed_transcripts_do_not_look_like_mock_output(root):
    run_dirs = [path.parent for path in Path(root).glob("*/aggregate_metrics.json")]
    flagged = {run_dir.name: run_dir_mock_reasons(run_dir)[:3] for run_dir in run_dirs}
    assert not {name: reasons for name, reasons in flagged.items() if reasons}


# Artifacts written before schema version 2 predate backend/temperature/error fields.
LEGACY_REQUIRED_FIELDS = ("run_id", "model", "intent_id", "condition", "timestamp", "status")


@pytest.mark.parametrize("root", COMMITTED_RUN_DIRS)
def test_committed_artifacts_have_run_metadata(root):
    for path in Path(root).glob("*/aggregate_metrics.json"):
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


@pytest.mark.parametrize("root", COMMITTED_RUN_DIRS)
def test_committed_summary_reports_provider_tokens_only(root):
    with Path(root, "summary.csv").open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {row["length_unit"] for row in rows} == {"provider_tokens"}


def test_rerun_matches_the_preregistered_design():
    payloads = [json.loads(p.read_text(encoding="utf-8")) for p in Path("artifacts_rerun").glob("*/aggregate_metrics.json")]
    assert len(payloads) == 200
    assert {p["model"] for p in payloads} == {"claude-sonnet-4-6"}
    assert {p["backend"] for p in payloads} == {"anthropic"}
    assert {p["temperature"] for p in payloads} == {0.2}
    assert {p["max_tokens"] for p in payloads} == {4096}
    assert {p["token_budget"] for p in payloads if p["condition"] == "budgeted"} == {120}
    cells = Counter((p["intent_id"], p["condition"]) for p in payloads)
    assert len(cells) == 20
    assert set(cells.values()) == {10}
