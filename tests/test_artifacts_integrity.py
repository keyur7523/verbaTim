from pathlib import Path
import csv


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
    assert any(name in header_lower for name in ["mean_tokens_per_turn", "mean_tokens", "mean_tokens_turn"])
    assert any(name in header_lower for name in ["drift_slope", "slope"])
    assert any(name in header_lower for name in ["growth_ratio", "growth"])
    assert any(name in header_lower for name in ["pass_rate", "pass"])


def test_backend_venv_not_present_and_ignored():
    assert not Path("backend/venv").exists()
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "backend/venv/" in gitignore
