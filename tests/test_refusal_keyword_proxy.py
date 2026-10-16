from verbatim.evaluators.refusal_keyword_proxy import evaluate_refusal_keyword_proxy


def test_no_keywords_not_flagged():
    result = evaluate_refusal_keyword_proxy("Here is a short response.")
    assert result["flagged"] is False
    assert result["details"]["match_type"] == "none"


def test_refusal_keyword_flagged():
    result = evaluate_refusal_keyword_proxy("Sorry, I can't help with that.")
    assert result["flagged"] is True
    assert result["details"]["match_type"] == "refusal_keyword"
    assert result["details"]["matched_keywords"] == ["can't"]


def test_brevity_keyword_flagged():
    result = evaluate_refusal_keyword_proxy("That would be too brief to be useful.")
    assert result["details"]["match_type"] == "brevity_keyword"


def test_empty_not_flagged():
    assert evaluate_refusal_keyword_proxy("")["flagged"] is False


# Known limits: these pin down that it is a keyword match, not refusal detection.

def test_known_false_positive_ordinary_answer_using_cannot():
    result = evaluate_refusal_keyword_proxy("You cannot mutate a tuple; build a new one instead.")
    assert result["flagged"] is True


def test_known_false_positive_budgeted_prompt_wording_echoed():
    # The budgeted system prompt itself says "If you cannot answer within the budget".
    assert evaluate_refusal_keyword_proxy("If you cannot answer within the budget, ask.")["flagged"] is True


def test_known_false_negative_refusal_without_keywords():
    result = evaluate_refusal_keyword_proxy("I'd rather not help with that request.")
    assert result["flagged"] is False
