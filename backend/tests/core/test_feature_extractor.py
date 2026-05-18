from __future__ import annotations

import pytest
from core.feature_extractor import (
    extract_features,
    get_feature_vector,
    FEATURE_ORDER,
    PATTERNS,
)


class TestExtractFeatures:
    """Unit tests for extract_features() — the core feature extraction logic."""

    def test_empty_string(self):
        """Empty or falsy input gets normalized to a single space."""
        feats = extract_features("")
        assert feats["char_count"] == 1.0
        assert feats["word_count"] == 0.0
        assert feats["sentence_count"] == 1.0
        # All pattern flags should be 0 for empty input
        for key in PATTERNS:
            assert feats[key] == 0.0, f"{key} should be 0 for empty input"
        assert feats["complexity_score"] == 0.0

    def test_simple_text(self):
        """Simple English text produces expected counts."""
        feats = extract_features("Hello world")
        assert feats["char_count"] == 11.0
        assert feats["word_count"] == 2.0
        assert feats["sentence_count"] > 0
        assert feats["avg_word_length"] > 0
        assert feats["complexity_score"] == 0.0  # Simple text, no patterns match

    def test_returns_all_feature_keys(self):
        """Returned dict contains every key listed in FEATURE_ORDER."""
        feats = extract_features("test")
        for key in FEATURE_ORDER:
            assert key in feats, f"Missing feature key: {key}"
        assert len(feats) == len(FEATURE_ORDER)

    def test_coding_keyword_detection(self):
        """Prompts with coding keywords set is_coding=1.0."""
        for kw in ["code", "implement", "function", "class", "algorithm",
                    "program", "script", "api", "return"]:
            feats = extract_features(f"Write a {kw} that sorts numbers")
            assert feats["is_coding"] == 1.0, f"'{kw}' should trigger is_coding"

    def test_debugging_keyword_detection(self):
        """Prompts with debugging keywords set is_debugging=1.0."""
        for kw in ["debug", "error", "traceback", "exception", "fix", "bug",
                    "crash", "segfault"]:
            feats = extract_features(f"I have a {kw} in my code")
            assert feats["is_debugging"] == 1.0, f"'{kw}' should trigger is_debugging"

    def test_reasoning_keyword_detection(self):
        """Prompts with reasoning keywords set is_reasoning=1.0."""
        for kw in ["explain", "why", "analyze", "compare", "difference", "evaluate"]:
            feats = extract_features(f"Can you {kw} these two concepts?")
            assert feats["is_reasoning"] == 1.0, f"'{kw}' should trigger is_reasoning"

    def test_creative_keyword_detection(self):
        feats = extract_features("Write a poem about a robot")
        assert feats["is_creative"] == 1.0

    def test_multistep_keyword_detection(self):
        for kw in ["design", "architecture", "plan", "roadmap", "build"]:
            feats = extract_features(f"Help me {kw} a scalable system")
            assert feats["is_multistep"] == 1.0, f"'{kw}' should trigger is_multistep"

    def test_math_keyword_detection(self):
        for kw in ["solve", "calculate", "equation", "probability", "proof"]:
            feats = extract_features(f"{kw} this math problem")
            assert feats["is_math"] == 1.0, f"'{kw}' should trigger is_math"

    def test_summarize_keyword_detection(self):
        for kw in ["summarize", "summary", "tldr", "brief", "overview", "condense"]:
            feats = extract_features(f"Can you {kw} this article?")
            assert feats["is_summarize"] == 1.0, f"'{kw}' should trigger is_summarize"

    def test_simple_qa_detection(self):
        feats = extract_features("What is the capital of France?")
        assert feats["is_simple_qa"] == 1.0

    def test_code_block_detection(self):
        feats = extract_features("Here is my code:\n```\nprint('hello')\n```")
        assert feats["has_code_block"] == 1.0

    def test_no_code_block(self):
        feats = extract_features("Hello world")
        assert feats["has_code_block"] == 0.0

    def test_number_detection(self):
        feats = extract_features("There are 42 apples and 7 oranges")
        assert feats["has_numbers"] == 1.0

    def test_no_numbers(self):
        feats = extract_features("Hello world")
        assert feats["has_numbers"] == 0.0

    def test_question_count(self):
        feats = extract_features("What? When? Where?")
        assert feats["question_count"] == 3.0

    def test_comma_count(self):
        feats = extract_features("apples, oranges, bananas, grapes")
        assert feats["comma_count"] == 3.0

    def test_bullet_detection(self):
        feats = extract_features("Things to do:\n- Buy milk\n- Walk dog")
        assert feats["has_bullet"] == 1.0

    def test_no_bullet_detection(self):
        feats = extract_features("Buy milk and walk dog")
        assert feats["has_bullet"] == 0.0

    def test_constraint_detection(self):
        for kw in ["must", "require", "limit", "only", "exactly"]:
            feats = extract_features(f"You {kw} use 3 sentences")
            assert feats["has_constraints"] == 1.0, f"'{kw}' should trigger has_constraints"

    def test_no_constraints(self):
        feats = extract_features("Hello world")
        assert feats["has_constraints"] == 0.0

    def test_caps_ratio(self):
        feats = extract_features("HELLO WORLD")
        assert feats["caps_ratio"] > 0.5

    def test_mixed_case_caps_ratio(self):
        feats = extract_features("Hello World")
        assert 0.0 < feats["caps_ratio"] < 1.0

    def test_no_caps(self):
        feats = extract_features("hello world")
        assert feats["caps_ratio"] == 0.0

    def test_complexity_score_coding(self):
        """Coding prompts should have higher complexity."""
        feats = extract_features("Implement a function that sorts an array using quicksort")
        assert feats["complexity_score"] >= 2.0  # is_coding gives 2.0

    def test_complexity_score_multistep(self):
        """Multistep prompts contribute more complexity."""
        feats = extract_features("Design a scalable architecture for a chat system")
        assert feats["complexity_score"] >= 2.5  # is_multistep gives 2.5

    def test_complexity_score_compound(self):
        """Compound patterns should stack complexity."""
        feats = extract_features(
            "Design and implement a function to fix the debug error in the algorithm"
        )
        assert feats["complexity_score"] >= 6.0

    def test_avg_word_length(self):
        """avg_word_length = char_count / word_count."""
        feats = extract_features("a b")  # 3 chars, 2 words
        assert feats["avg_word_length"] == pytest.approx(1.5)

    def test_unique_word_ratio(self):
        """unique_word_ratio = unique_word_count / word_count."""
        feats = extract_features("the the the")  # 1 unique, 3 words
        assert feats["unique_word_ratio"] == pytest.approx(1.0 / 3.0)

    def test_fk_grade_is_float(self):
        feats = extract_features("A long complex sentence that is harder to read and understand properly.")
        assert isinstance(feats["fk_grade"], float)
        assert feats["fk_grade"] > 0

    def test_multiple_patterns_can_match(self):
        """A single prompt can match multiple pattern categories."""
        feats = extract_features("Debug the function that calculates pi and explain why it fails")
        assert feats["is_debugging"] == 1.0
        assert feats["is_coding"] == 1.0
        assert feats["is_reasoning"] == 1.0

    def test_very_long_text(self):
        """Very long text should not crash."""
        text = "word " * 10000
        feats = extract_features(text)
        assert feats["word_count"] == 10000
        assert feats["complexity_score"] >= 0

    def test_text_with_only_numbers(self):
        feats = extract_features("42 7 100 3")
        assert feats["has_numbers"] == 1.0
        assert feats["is_coding"] == 0.0
        assert feats["is_debugging"] == 0.0

    def test_text_with_special_characters(self):
        feats = extract_features("!@#$%^&*()")
        assert feats["char_count"] > 0
        # No actual words
        assert isinstance(feats["word_count"], float)

    def test_whitespace_only(self):
        feats = extract_features("   \n  \t  ")
        # Should not crash, word counts safely handled
        assert "char_count" in feats


class TestGetFeatureVector:
    """Unit tests for get_feature_vector()."""

    def test_returns_list(self):
        vec = get_feature_vector("test")
        assert isinstance(vec, list)

    def test_length_matches_feature_order(self):
        vec = get_feature_vector("test")
        assert len(vec) == len(FEATURE_ORDER)

    def test_order_matches_feature_order(self):
        """Vector values match the order defined in FEATURE_ORDER."""
        feats = extract_features("Hello world coding test")
        vec = get_feature_vector("Hello world coding test")
        for i, key in enumerate(FEATURE_ORDER):
            assert vec[i] == feats[key], f"Mismatch at index {i} for key '{key}': {vec[i]} != {feats[key]}"

    def test_empty_string(self):
        """Empty string produces a vector of correct length without error."""
        vec = get_feature_vector("")
        assert len(vec) == len(FEATURE_ORDER)
        # The text is normalized to " " internally
        assert vec[0] == 1.0  # char_count should be 1

    def test_none_coerced_to_empty(self):
        """None should not crash due to 'if not text' guard."""
        vec = get_feature_vector(None)  # type: ignore[arg-type]
        assert len(vec) == len(FEATURE_ORDER)

    def test_all_values_are_floats(self):
        vec = get_feature_vector("test")
        for v in vec:
            assert isinstance(v, float), f"Value {v} is not float"

    def test_stable_across_calls(self):
        """Same input produces identical output."""
        v1 = get_feature_vector("Hello world, implement a function")
        v2 = get_feature_vector("Hello world, implement a function")
        assert v1 == v2
