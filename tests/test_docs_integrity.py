from pathlib import Path
import re


def test_case_study_has_results_table_and_deltas_or_todos():
    content = Path("docs/case-study.md").read_text(encoding="utf-8")
    assert "### Results (Summary)" in content
    assert "| Condition | Mean tokens/turn | Drift slope (tokens/turn) | Growth ratio | Pass rate (verbosity) |" in content
    assert "### Deltas (baseline → verbatim)" in content

    has_digit = re.search(r"\d", content) is not None
    has_todo = "TODO:" in content
    assert has_digit or has_todo


def test_case_study_does_not_imply_unimplemented_metrics():
    content = Path("docs/case-study.md").read_text(encoding="utf-8")
    assert "Verbosity reduction alone is insufficient without safety and adherence checks." in content
    assert "Safety-adjacent checks (status)" in content
    lowered = content.lower()
    assert "planned" in lowered or "not implemented" in lowered


def test_reproducibility_has_required_sections_and_commands():
    content = Path("docs/reproducibility.md").read_text(encoding="utf-8")
    for label in [
        "Environment",
        "Model Configuration",
        "Dataset Description",
        "Execution Steps",
        "Artifacts",
        "Determinism & Variance",
        "Known Limitations",
    ]:
        assert label in content

    assert "ANTHROPIC_API_KEY" in content

    lines = content.splitlines()
    command_like = 0
    python_lines = 0
    for line in lines:
        if line.strip().startswith("$ ") or "python" in line or "uvicorn" in line:
            command_like += 1
        if "python" in line:
            python_lines += 1

    assert python_lines >= 2
    assert command_like >= 3
