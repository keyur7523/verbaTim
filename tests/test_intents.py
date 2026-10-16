from verbatim.experiments.run_conversations import build_turn_specs, build_turns, load_intents


KNOWN_SPEC_KEYS = {
    "max_words",
    "max_sentences",
    "max_lines",
    "required_format",
    "bullet_count",
    "bullets_only",
    "forbidden_phrases",
}


def test_every_intent_has_twelve_turns_with_aligned_specs():
    for intent in load_intents()["intents"]:
        turns = build_turns(intent)
        specs = build_turn_specs(intent)
        assert len(turns) == 12, intent["id"]
        assert len(specs) == len(turns), intent["id"]
        assert all(isinstance(turn, str) and turn for turn in turns), intent["id"]


def test_every_intent_has_checkable_turns_with_known_keys():
    for intent in load_intents()["intents"]:
        specs = [spec for spec in build_turn_specs(intent) if spec]
        assert specs, intent["id"]
        for spec in specs:
            assert set(spec) <= KNOWN_SPEC_KEYS, (intent["id"], spec)
