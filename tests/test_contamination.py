import json
from pathlib import Path

from verbatim.analysis.contamination import mock_echo_reason, run_dir_mock_reasons
from verbatim.analysis.summarize import summarize


USER = "Explain what a hash table is and when to use it."


def test_flags_system_prompt_echo():
    text = f"You are a helpful assistant.\nBe concise.\n\n{USER}"
    assert mock_echo_reason(text, USER) == "echoes_system_prompt"


def test_flags_system_prompt_echo_truncated_to_budget():
    text = "You are a helpful assistant. Keep each response within 80 tokens. If you"
    assert mock_echo_reason(text, USER) == "echoes_system_prompt"


def test_flags_prefixed_user_echo():
    assert mock_echo_reason(f"Answer: {USER}", USER) == "echoes_user_text"
    assert mock_echo_reason(f"Verbatim answer: {USER}", USER) == "echoes_user_text"


def test_flags_fixed_fallback_text():
    assert mock_echo_reason("Clarify: which detail is most important?", USER) == "mock_fallback_text"


def test_real_reply_is_not_flagged():
    text = (
        "A hash table maps keys to values using a hash function, giving average O(1) "
        "lookup. Use it when you need fast membership checks or key-based access."
    )
    assert mock_echo_reason(text, USER) is None


def test_reply_quoting_the_question_mid_text_is_not_flagged():
    text = f'You asked: "{USER}" A hash table maps keys to values.'
    assert mock_echo_reason(text, USER) is None


def test_short_user_text_ending_a_reply_is_not_flagged():
    assert mock_echo_reason("Sure, here is the summary. Thanks!", "Thanks!") is None


def test_summary_excludes_mock_content_under_real_model_id(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    payload = {
        "run_id": "run-1",
        "model": "claude-sonnet-4-20250514",
        "condition": "baseline",
        "status": "completed",
        "passed": True,
        "metrics": {"metrics": {"mean_tokens_per_turn": 12.0, "drift_slope": 0.0, "length_stddev": 0.0}},
    }
    (run_dir / "aggregate_metrics.json").write_text(json.dumps(payload), encoding="utf-8")
    transcript = [{"turn_index": 0, "user_text": USER, "assistant_text": f"Answer: {USER}"}]
    (run_dir / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")

    assert run_dir_mock_reasons(run_dir) == [(0, "echoes_user_text")]
    rows, excluded = summarize(tmp_path)
    assert rows == []
    assert excluded == {"mock_content": 1}


def test_summary_never_pools_words_with_tokens(tmp_path: Path):
    def write_run(name: str, extra: dict) -> None:
        run_dir = tmp_path / name
        run_dir.mkdir()
        payload = {
            "run_id": name,
            "model": "claude-sonnet-4-20250514",
            "condition": "baseline",
            "status": "completed",
            "passed": False,
            "metrics": {"metrics": {"mean_tokens_per_turn": 10.0, "drift_slope": 0.0, "length_stddev": 0.0}},
            **extra,
        }
        (run_dir / "aggregate_metrics.json").write_text(json.dumps(payload), encoding="utf-8")

    write_run("tokens", {"length_unit": "provider_tokens"})
    write_run("words", {"length_unit": "words"})
    rows, _ = summarize(tmp_path)
    assert sorted((row["length_unit"], row["n"]) for row in rows) == [("provider_tokens", 1), ("words", 1)]
