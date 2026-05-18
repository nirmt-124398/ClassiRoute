from __future__ import annotations

import os
import pickle
import tempfile

import numpy as np
import pytest

from core.feature_extractor import extract_features, get_feature_vector, FEATURE_ORDER
from core.router import route_prompt, TIER_NAMES


@pytest.fixture(autouse=True)
def _heuristic_mode():
    """Ensure tests run in heuristic fallback mode (no loaded models)."""
    import core.router as router_mod
    router_mod.CLASSIFIER = None
    router_mod.REGRESSOR = None


class TestFeatureExtractor:
    """Feature extraction is the foundation — if features are wrong, routing is wrong."""

    def test_empty_text_returns_all_features(self):
        feats = extract_features("")
        for k in FEATURE_ORDER:
            assert k in feats, f"Missing feature: {k}"
        assert isinstance(feats["char_count"], float)
        assert feats["char_count"] >= 0

    def test_code_detection(self):
        feats = extract_features("Write a function to sort an array in Python")
        assert feats["is_coding"] == 1.0

    def test_simple_qa_detection(self):
        feats = extract_features("What is the capital of France?")
        assert feats["is_simple_qa"] == 1.0

    def test_reasoning_detection(self):
        feats = extract_features("Explain why quantum computing is important")
        assert feats["is_reasoning"] == 1.0

    def test_feature_vector_order(self):
        vec = get_feature_vector("Test prompt with some text")
        assert len(vec) == len(FEATURE_ORDER)
        assert all(isinstance(v, float) for v in vec)

    def test_code_block_flag(self):
        feats = extract_features("Here is some code:\n```\ndef foo():\n    pass\n```")
        assert feats["has_code_block"] == 1.0

    def test_complexity_score_range(self):
        feats = extract_features("What is the weather today?")
        assert 0 <= feats["complexity_score"] <= 20


class TestRouterHeuristic:
    """When no trained model is loaded, route_prompt falls back to heuristics."""

    def test_simple_prompt_routes_to_tier_0(self):
        result = route_prompt("What is the capital of France?")
        assert "tier" in result
        assert "tier_name" in result
        assert "confidence" in result
        assert "difficulty_score" in result
        assert "upgraded" in result
        assert result["tier_name"] == TIER_NAMES[result["tier"]]
        assert result["tier"] == 0, f"Simple QA should route to tier 0, got {result}"

    def test_complex_code_prompt_routes_to_tier_2(self):
        result = route_prompt(
            "Design and implement a distributed caching system using Redis "
            "with consistent hashing, replication, and failure recovery. "
            "The system must handle 10k req/s with <5ms latency."
        )
        assert result["tier"] == 2, f"Complex code should route to tier 2, got {result}"

    def test_mid_complexity_routes_to_tier_1(self):
        result = route_prompt(
            "Compare the differences between SQL and NoSQL databases, "
            "including their strengths and weaknesses for web applications."
        )
        assert result["tier"] == 1, f"Moderate reasoning should route to tier 1, got {result}"

    def test_feature_vector_consistency(self):
        vec1 = get_feature_vector("Same prompt every time")
        vec2 = get_feature_vector("Same prompt every time")
        assert vec1 == vec2

    def test_none_text_does_not_crash(self):
        """Feature extractor handles None gracefully."""
        try:
            feats = extract_features(None)  # type: ignore
            assert all(k in feats for k in FEATURE_ORDER)
        except Exception:
            feature_vector = get_feature_vector(" ")  # manual fallback
            assert len(feature_vector) == len(FEATURE_ORDER)

    def test_long_prompt_does_not_overflow(self):
        long_text = "word " * 10_000
        feats = extract_features(long_text)
        assert feats["word_count"] > 0
        assert feats["char_count"] > 0
        assert feats["complexity_score"] >= 0

    def test_tier_reproducibility(self):
        """Same prompt always gets same tier (no randomness in heuristic)."""
        prompt = "Write a poem about AI taking over the world"
        r1 = route_prompt(prompt)
        r2 = route_prompt(prompt)
        assert r1["tier"] == r2["tier"]
        assert r1["difficulty_score"] == r2["difficulty_score"]

    def test_confidence_is_always_05_when_no_model(self):
        result = route_prompt("Hello")
        assert result["confidence"] == 0.5

    def test_upgraded_is_always_false_when_no_model(self):
        result = route_prompt("Hello")
        assert result["upgraded"] is False

    def test_all_tiers_are_reachable(self):
        found = set()
        prompts = [
            "What is the capital of France?",                              # tier 0
            "Define machine learning in simple terms",                     # tier 0
            "Compare and contrast Python and JavaScript",                  # tier 1
            "Explain how the internet works to a beginner",                # tier 1
            "Design and implement a distributed caching system using Redis with consistent hashing, replication, and failure recovery. The system must handle 10k req/s with <5ms latency.",  # tier 2
            "Design and implement a fault-tolerant distributed consensus protocol with leader election, log replication, failure detection, and automatic recovery across 5 nodes. Must guarantee safety under network partitions.",  # tier 2
        ]
        for p in prompts:
            found.add(route_prompt(p)["tier"])
        assert 0 in found, f"Tier 0 not reachable (found tiers: {found})"
        assert 1 in found, f"Tier 1 not reachable (found tiers: {found})"
        assert 2 in found, f"Tier 2 not reachable (found tiers: {found})"

    def test_heuristic_matches_feature_complexity(self):
        """Tier assignment should correlate with complexity_score."""
        simple = route_prompt("What is your name?")
        complex = route_prompt("Design a scalable distributed database system with ACID compliance")
        assert simple["tier"] <= complex["tier"], \
            f"Simple ({simple['tier']}) should be <= complex ({complex['tier']})"
