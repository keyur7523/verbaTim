from verbatim.evaluators.refusal import evaluate_refusal


def test_refusal_pass():
    result = evaluate_refusal("Here is a short response.")
    assert result["refusal_detected"] is False
    assert result["details"]["refusal_type"] == "none"


def test_refusal_fail():
    result = evaluate_refusal("Sorry, I can't help with that.")
    assert result["refusal_detected"] is True
    assert result["details"]["refusal_type"] == "hard_refusal"


def test_refusal_edge_empty():
    result = evaluate_refusal("")
    assert result["refusal_detected"] is False
