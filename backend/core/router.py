import logging
import os
import pickle
import numpy as np
from core.feature_extractor import extract_features, get_feature_vector

logger = logging.getLogger(__name__)

CLASSIFIER = None
REGRESSOR  = None
CONFIDENCE_THRESHOLD = 0.60
TIER_NAMES = {0: "weak", 1: "mid", 2: "strong"}

def load_models():
    """Load classifier and regressor models from disk.

    Gracefully handles missing or corrupt model files — sets CLASSIFIER
    and REGRESSOR to None instead of crashing.
    """
    global CLASSIFIER, REGRESSOR
    classifier_path = "core/models/router_classifier.pkl"
    regressor_path = "core/models/router_regressor.pkl"

    if os.path.exists(classifier_path):
        try:
            with open(classifier_path, "rb") as f:
                CLASSIFIER = pickle.load(f)
            logger.info("Classifier loaded from %s", classifier_path)
        except Exception as exc:
            logger.warning("Failed to load classifier: %s", exc)
    else:
        logger.warning("Classifier not found at %s — running without ML", classifier_path)

    if os.path.exists(regressor_path):
        try:
            with open(regressor_path, "rb") as f:
                REGRESSOR = pickle.load(f)
            logger.info("Regressor loaded from %s", regressor_path)
        except Exception as exc:
            logger.warning("Failed to load regressor: %s", exc)
    else:
        logger.warning("Regressor not found at %s — running without ML", regressor_path)


def _heuristic_route(prompt: str) -> dict:
    """Fallback routing when no ML classifier is available.

    Uses the feature extractor's complexity_score to assign a tier:
        score < 2  → tier 0 (weak)
        score < 4  → tier 1 (mid)
        else       → tier 2 (strong)
    """
    feats = extract_features(prompt)
    score = feats["complexity_score"]
    features = get_feature_vector(prompt)

    if score < 2.0:
        tier = 0
    elif score < 4.0:
        tier = 1
    else:
        tier = 2

    if REGRESSOR is not None:
        difficulty = float(REGRESSOR.predict([features])[0])
    else:
        difficulty = min(score / 10.0, 1.0)

    logger.info("Heuristic route: complexity_score=%.2f → tier=%d", score, tier)

    return {
        "tier"            : tier,
        "tier_name"       : TIER_NAMES[tier],
        "confidence"      : 0.5,
        "difficulty_score": round(difficulty, 4),
        "upgraded"        : False,
        "rerouted"        : False,
    }


def route_prompt(prompt: str) -> dict:
    # --- Heuristic fallback when no classifier is loaded ---
    if CLASSIFIER is None:
        return _heuristic_route(prompt)

    features = get_feature_vector(prompt)

    # predict_proba expects 2D array, returns 2D array
    probs = CLASSIFIER.predict_proba([features])[0]
    tier = int(np.argmax(probs))
    confidence = float(probs[tier])

    logger.info("ML prediction: tier=%d conf=%.4f probs=%s", tier, confidence, probs.tolist())

    if REGRESSOR is not None:
        # expect 2D array, returns 1D array
        difficulty = float(REGRESSOR.predict([features])[0])
    else:
        difficulty = min(extract_features(prompt)["complexity_score"] / 10.0, 1.0)

    upgraded = False
    if confidence < CONFIDENCE_THRESHOLD and tier < 2:
        tier += 1
        upgraded = True
        logger.info("Low confidence (%.4f < %.2f), upgraded tier %d → %d", confidence, CONFIDENCE_THRESHOLD, tier - 1, tier)

    return {
        "tier"            : tier,
        "tier_name"       : TIER_NAMES[tier],
        "confidence"      : round(confidence, 4),
        "difficulty_score": round(difficulty, 4),
        "upgraded"        : upgraded,
        "rerouted"        : False,
    }
