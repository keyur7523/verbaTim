from verbatim.evaluators.instruction_adherence import evaluate_instruction_adherence


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
