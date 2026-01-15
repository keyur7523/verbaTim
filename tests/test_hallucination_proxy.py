from verbatim.evaluators.hallucination_proxy import evaluate_hallucination_proxy


def test_hallucination_proxy_pass_with_context():
    context = "Alice works at Acme Corp in 2024."
    result = evaluate_hallucination_proxy("Alice joined Acme Corp in 2024.", context)
    assert result["passed"] is True
    assert result["details"]["flagged_spans"] == []


def test_hallucination_proxy_fail_with_context():
    context = "Alice works at Acme Corp in 2024."
    result = evaluate_hallucination_proxy("Bob joined Acme Corp in 2025.", context)
    assert result["passed"] is False
    assert "Bob" in result["details"]["flagged_spans"]
    assert "2025" in result["details"]["flagged_spans"]


def test_hallucination_proxy_edge_empty():
    result = evaluate_hallucination_proxy("", None)
    assert result["passed"] is True
