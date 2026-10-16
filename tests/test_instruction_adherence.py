from verbatim.evaluators.instruction_adherence import (
    evaluate_instruction_adherence,
    evaluate_transcript_adherence,
)


def test_instruction_adherence_pass():
    spec = {"max_words": 10, "required_format": "short_paragraphs", "forbidden_phrases": ["nope"]}
    result = evaluate_instruction_adherence("Short answer.", spec)
    assert result["passed"] is True
    assert result["details"]["violations"] == []


def test_instruction_adherence_fail():
    spec = {"max_words": 2, "required_format": "bullets", "forbidden_phrases": ["forbidden"]}
    result = evaluate_instruction_adherence("Forbidden phrase here.", spec)
    assert result["passed"] is False
    assert "max_words_exceeded" in result["details"]["violations"]
    assert "format_mismatch" in result["details"]["violations"]
    assert "forbidden_phrase:forbidden" in result["details"]["violations"]


def test_instruction_adherence_edge_empty():
    spec = {"max_words": 1, "required_format": "short_paragraphs"}
    result = evaluate_instruction_adherence("", spec)
    assert result["passed"] is True


def test_one_sentence_violation_detected():
    result = evaluate_instruction_adherence("Hash tables are fast. They use hashing.", {"max_sentences": 1})
    assert result["passed"] is False
    assert result["details"]["violations"] == ["max_sentences_exceeded"]


def test_decimals_and_big_o_do_not_split_sentences():
    result = evaluate_instruction_adherence("Lookup is O(1) on average, about 3.5x faster here.", {"max_sentences": 1})
    assert result["passed"] is True


def test_one_line_violation_detected():
    result = evaluate_instruction_adherence("Recap:\nHash tables trade memory for speed.", {"max_lines": 1})
    assert result["details"]["violations"] == ["max_lines_exceeded"]


def test_two_bullets_counts_numbered_items_and_flags_three():
    assert evaluate_instruction_adherence("1. REST\n2. GraphQL", {"bullet_count": 2})["passed"] is True
    result = evaluate_instruction_adherence("- a\n- b\n- c", {"required_format": "bullets", "bullet_count": 2})
    assert result["details"]["violations"] == ["bullet_count_mismatch"]


def test_bullets_only_rejects_prose_but_allows_sub_bullets():
    spec = {"required_format": "bullets", "bullets_only": True}
    assert evaluate_instruction_adherence("- a\n  - detail\n- b", spec)["passed"] is True
    result = evaluate_instruction_adherence("Here are the points:\n- a\n- b", spec)
    assert result["details"]["violations"] == ["non_bullet_lines"]


def test_no_spec_is_reported_as_unchecked():
    result = evaluate_instruction_adherence("Anything at all, however long.", None)
    assert result["passed"] is True
    assert result["details"]["checked"] is False


def test_transcript_adherence_only_checks_turns_with_a_spec():
    transcript = [
        {"turn_index": 0, "assistant_text": "Long opening answer. With several sentences. And more."},
        {"turn_index": 1, "assistant_text": "One sentence. Then another."},
        {"turn_index": 2, "assistant_text": "- a\n- b"},
    ]
    specs = [None, {"max_sentences": 1}, {"bullet_count": 2}]
    result = evaluate_transcript_adherence(transcript, specs)
    assert result["checked_turns"] == 2
    assert result["passed_turns"] == 1
    assert result["passed"] is False
    assert [turn["turn_index"] for turn in result["per_turn"]] == [1, 2]
