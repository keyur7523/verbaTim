from verbatim.evaluators.unsupported_claim_proxy import evaluate_unsupported_claim_proxy


def test_supported_spans_pass_with_context():
    context = "Alice works at Acme Corp in 2024."
    result = evaluate_unsupported_claim_proxy("Alice joined Acme Corp in 2024.", context)
    assert result["passed"] is True
    assert result["details"]["flagged_spans"] == []


def test_unsupported_spans_flagged_with_context():
    context = "Alice works at Acme Corp in 2024."
    result = evaluate_unsupported_claim_proxy("Bob joined Acme Corp in 2025.", context)
    assert result["passed"] is False
    assert "Bob" in result["details"]["flagged_spans"]
    assert "2025" in result["details"]["flagged_spans"]


def test_empty_passes():
    result = evaluate_unsupported_claim_proxy("", None)
    assert result["passed"] is True


# Known limits: these pin down that it is a regex proxy, not hallucination detection.

def test_known_false_positive_sentence_initial_word():
    context = "Alice works at Acme Corp."
    result = evaluate_unsupported_claim_proxy("The company employs Alice.", context)
    assert result["details"]["flagged_spans"] == ["The"]


def test_known_false_positive_correct_fact_without_context():
    result = evaluate_unsupported_claim_proxy("Average lookup in a hash table is O(1).", None)
    assert result["passed"] is False
    assert result["details"]["reason_codes"] == ["numeric_claim"]


def test_known_false_negative_fabricated_lowercase_claim():
    context = "Alice works at Acme Corp."
    result = evaluate_unsupported_claim_proxy("Alice was recently fired for fraud.", context)
    assert result["passed"] is True
