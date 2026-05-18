from __future__ import annotations

import os
import pickle
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyClassifier, DummyRegressor


# We need to reset the module globals before each test.
@pytest.fixture(autouse=True)
def _reset_router_globals():
    """Reset CLASSIFIER and REGRESSOR before/after each test."""
    import core.router as router_mod
    saved_clf = router_mod.CLASSIFIER
    saved_reg = router_mod.REGRESSOR
    router_mod.CLASSIFIER = None
    router_mod.REGRESSOR = None
    yield
    router_mod.CLASSIFIER = saved_clf
    router_mod.REGRESSOR = saved_reg


class TestLoadModels:
    """Unit tests for load_models()."""

    def test_loads_models_successfully(self):
        """Loads both classifier and regressor from packaged model files."""
        import core.router as router_mod
        router_mod.load_models()
        assert router_mod.CLASSIFIER is not None
        assert router_mod.REGRESSOR is not None
        # Verify they can predict
        features = [0.0] * 23
        probs = router_mod.CLASSIFIER.predict_proba([features])[0]
        assert len(probs) == 3
        diff = router_mod.REGRESSOR.predict([features])[0]
        assert isinstance(diff, (float, np.floating))

    def test_graceful_when_classifier_missing(self):
        """Sets CLASSIFIER to None instead of crashing when file is missing."""
        from core.router import load_models
        import core.router as router_mod
        original_exists = os.path.exists

        def fake_exists(path):
            if "classifier" in path:
                return False
            return original_exists(path)

        with patch.object(os.path, "exists", side_effect=fake_exists):
            load_models()
            assert router_mod.CLASSIFIER is None

    def test_graceful_when_regressor_missing(self):
        """Sets REGRESSOR to None instead of crashing when file is missing."""
        from core.router import load_models
        import core.router as router_mod
        original_exists = os.path.exists

        def fake_exists(path):
            if "regressor" in path:
                return False
            return original_exists(path)

        with patch.object(os.path, "exists", side_effect=fake_exists):
            load_models()
            assert router_mod.REGRESSOR is None


class TestRoutePrompt:
    """Unit tests for route_prompt()."""

    @pytest.fixture(autouse=True)
    def _setup_mock_models(self):
        """Set up mock CLASSIFIER and REGRESSOR with controlled behavior."""
        import core.router as router_mod

        # Default: tier 1 (mid), confidence 0.85 (above threshold), difficulty 0.5
        self.mock_classifier = MagicMock()
        self.mock_classifier.predict_proba.return_value = np.array([[0.10, 0.85, 0.05]])
        self.mock_regressor = MagicMock()
        self.mock_regressor.predict.return_value = np.array([0.5])

        router_mod.CLASSIFIER = self.mock_classifier
        router_mod.REGRESSOR = self.mock_regressor
        yield

    def test_returns_expected_keys(self):
        """route_prompt() returns a dict with all required keys."""
        from core.router import route_prompt
        result = route_prompt("Hello world")
        assert isinstance(result, dict)
        assert "tier" in result
        assert "tier_name" in result
        assert "confidence" in result
        assert "difficulty_score" in result
        assert "upgraded" in result

    def test_high_confidence_no_upgrade(self):
        """When confidence >= 0.60, no upgrade happens."""
        from core.router import route_prompt
        # predict_proba returns: [0.10, 0.85, 0.05] → tier=1, confidence=0.85
        result = route_prompt("Hello world")
        assert result["tier"] == 1
        assert result["tier_name"] == "mid"
        assert result["confidence"] == 0.85
        assert result["upgraded"] is False

    def test_low_confidence_upgrades_tier(self):
        """When confidence < 0.60 and tier < 2, upgrade one level: weak→mid."""
        import core.router as router_mod
        # argmax of [0.40, 0.35, 0.25] = 0 (weak), confidence=0.40 < 0.60 → upgrade to 1
        self.mock_classifier.predict_proba.return_value = np.array([[0.40, 0.35, 0.25]])
        result = router_mod.route_prompt("hard prompt")
        assert result["tier"] == 1
        assert result["tier_name"] == "mid"
        assert result["upgraded"] is True

    def test_low_confidence_upgrades_from_mid_to_strong(self):
        """When confidence < 0.60 for tier 1, upgrade to tier 2."""
        import core.router as router_mod
        # argmax of [0.30, 0.40, 0.30] = 1 (mid), confidence=0.40 < 0.60 → upgrade to 2
        self.mock_classifier.predict_proba.return_value = np.array([[0.30, 0.40, 0.30]])
        result = router_mod.route_prompt("hard prompt")
        assert result["tier"] == 2
        assert result["tier_name"] == "strong"
        assert result["upgraded"] is True

    def test_no_upgrade_when_already_strong(self):
        """When tier is already strong (2), never upgrade even if confidence is low."""
        import core.router as router_mod
        # argmax of [0.20, 0.30, 0.50] = 2 (strong), confidence=0.50 < 0.60
        # but tier=2 is already max → no upgrade
        self.mock_classifier.predict_proba.return_value = np.array([[0.20, 0.30, 0.50]])
        result = router_mod.route_prompt("hard prompt")
        assert result["tier"] == 2, "Tier 2 should never upgrade"
        assert result["tier_name"] == "strong"
        assert result["upgraded"] is False

    def test_confidence_at_threshold_no_upgrade(self):
        """Confidence exactly at 0.60 should NOT trigger upgrade."""
        import core.router as router_mod
        self.mock_classifier.predict_proba.return_value = np.array([[0.60, 0.30, 0.10]])
        result = router_mod.route_prompt("test")
        assert result["tier"] == 0
        assert result["upgraded"] is False

    def test_confidence_just_below_threshold_upgrades(self):
        """Confidence just below 0.60 should trigger upgrade."""
        import core.router as router_mod
        # tier 0, confidence 0.5999
        self.mock_classifier.predict_proba.return_value = np.array([[0.5999, 0.3000, 0.1001]])
        result = router_mod.route_prompt("test")
        assert result["upgraded"] is True
        assert result["tier"] == 1

    def test_difficulty_score_from_regressor(self):
        """difficulty_score comes from regressor predict."""
        import core.router as router_mod
        self.mock_regressor.predict.return_value = np.array([0.85])
        result = router_mod.route_prompt("test")
        assert result["difficulty_score"] == 0.85

    def test_confidence_rounded_to_4_decimals(self):
        """Confidence values are rounded to 4 decimal places."""
        import core.router as router_mod
        self.mock_classifier.predict_proba.return_value = np.array([[0.12345678, 0.80012345, 0.07641977]])
        result = router_mod.route_prompt("test")
        assert result["confidence"] == 0.8001  # rounded to 4 decimal places

    def test_upgrade_flag_only_set_when_actually_upgraded(self):
        """upgrade flag should be True only when an actual upgrade happened."""
        import core.router as router_mod
        # High confidence case
        self.mock_classifier.predict_proba.return_value = np.array([[0.10, 0.85, 0.05]])
        result = router_mod.route_prompt("test")
        assert result["upgraded"] is False

        # Low confidence, upgrade triggered
        self.mock_classifier.predict_proba.return_value = np.array([[0.30, 0.50, 0.20]])
        result = router_mod.route_prompt("test")
        assert result["upgraded"] is True

    def test_weak_confidence_upgrade_no_change_to_tier_name_map(self):
        """After upgrade from weak→mid, tier_name should reflect final tier."""
        import core.router as router_mod
        # argmax of [0.40, 0.35, 0.25] = 0 (weak), confidence=0.40 < 0.60 → upgrade to 1 (mid)
        self.mock_classifier.predict_proba.return_value = np.array([[0.40, 0.35, 0.25]])
        result = router_mod.route_prompt("prompt")
        assert result["tier_name"] == "mid"
        assert result["tier"] == 1

    def test_empty_prompt_routes_gracefully(self):
        """Empty prompt should not crash the router."""
        import core.router as router_mod
        result = router_mod.route_prompt("")
        assert isinstance(result, dict)
        assert "tier" in result

    def test_very_long_prompt(self):
        """Very long prompts should route without error."""
        import core.router as router_mod
        result = router_mod.route_prompt("word " * 5000)
        assert isinstance(result, dict)
        assert "tier" in result
