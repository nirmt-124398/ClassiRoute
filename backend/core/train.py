"""
ML training pipeline for the prompt router.

Trains an XGBoost classifier (tier prediction) and regressor (difficulty score)
on synthetic seed data or from actual DB request logs.

Usage:
    python -m core.train --seed    # synthetic data (recommended)
    python -m core.train            # try DB, fallback to synthetic
"""

from __future__ import annotations

import argparse
import os
import pickle

import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier, XGBRegressor

from core.feature_extractor import get_feature_vector, FEATURE_ORDER

# ---------------------------------------------------------------------------
# Seed data — synthetic prompts mapped to ground-truth tiers & difficulty
# ---------------------------------------------------------------------------
# Each entry: (prompt, tier, difficulty)

TIER_0_SEED: list[tuple[str, int, float]] = [
    # --- simple QA ---
    ("What is the capital of France?", 0, 0.15),
    ("Define machine learning in simple terms", 0, 0.25),
    ("Who wrote Romeo and Juliet?", 0, 0.10),
    ("What is the speed of light in a vacuum?", 0, 0.15),
    ("Explain what photosynthesis is", 0, 0.20),
    ("What is the tallest mountain on Earth?", 0, 0.10),
    ("What year did World War II end?", 0, 0.10),
    ("Define the term ecosystem", 0, 0.15),
    ("What is the chemical symbol for gold?", 0, 0.10),
    ("Who is the current president of the United States?", 0, 0.10),
    ("What is the difference between weather and climate?", 0, 0.25),
    ("What is the boiling point of water in Celsius?", 0, 0.10),
    ("Define what a mammal is", 0, 0.15),
    ("What is the largest ocean on Earth?", 0, 0.10),
    ("How many bones are in the human body?", 0, 0.15),
    ("What is the Pythagorean theorem?", 0, 0.20),
    ("Who discovered penicillin?", 0, 0.10),
    ("What is the currency of Japan?", 0, 0.10),
    ("Define inertia in physics", 0, 0.20),
    ("What language is spoken in Brazil?", 0, 0.10),
    # --- summarization ---
    ("Summarize this article about climate change", 0, 0.20),
    ("Give me a brief overview of the French Revolution", 0, 0.25),
    ("Can you summarize the plot of Hamlet in three sentences?", 0, 0.20),
    ("TLDR: what is the main idea of this paragraph?", 0, 0.15),
    ("Condense this report into a short executive summary", 0, 0.25),
    ("Briefly explain the concept of gravity for a child", 0, 0.20),
    ("Write a one-paragraph summary of the water cycle", 0, 0.20),
    ("Summarize the key points from this meeting notes", 0, 0.20),
    ("Give me a quick overview of how batteries work", 0, 0.25),
    ("What is the main takeaway from this news article?", 0, 0.15),
    ("Summarize the plot of 1984 by George Orwell", 0, 0.20),
    ("Write a brief description of the solar system", 0, 0.20),
]

TIER_1_SEED: list[tuple[str, int, float]] = [
    # --- reasoning ---
    ("Compare and contrast Python and JavaScript for web development", 1, 0.50),
    ("Explain how the internet works to someone with no technical background", 1, 0.45),
    ("What are the ethical implications of artificial intelligence?", 1, 0.55),
    ("Analyze the themes of power and corruption in Animal Farm", 1, 0.50),
    ("Why does democracy require an informed electorate to function well?", 1, 0.50),
    ("Explain the difference between causation and correlation with examples", 1, 0.55),
    ("How does supply and demand affect pricing in a free market?", 1, 0.45),
    ("What factors led to the fall of the Roman Empire?", 1, 0.50),
    ("Evaluate the pros and cons of remote work versus office work", 1, 0.45),
    ("Why is biodiversity important for ecosystem health?", 1, 0.40),
    ("How do vaccines work to protect against diseases?", 1, 0.45),
    ("Analyze the causes and effects of income inequality", 1, 0.55),
    ("What are the trade-offs between nuclear and solar energy?", 1, 0.50),
    ("Explain the concept of opportunity cost in economics", 1, 0.45),
    ("How does cognitive bias affect decision-making in business?", 1, 0.55),
    ("Compare the educational systems of Finland and the United States", 1, 0.55),
    ("Why do some countries develop faster than others?", 1, 0.50),
    ("Explain how encryption protects data during online transactions", 1, 0.55),
    ("What are the arguments for and against universal basic income?", 1, 0.60),
    ("Analyze how social media has changed political communication", 1, 0.55),
    # --- creative writing ---
    ("Write a short story about a time traveler who meets their past self", 1, 0.50),
    ("Compose a poem about autumn leaves falling in a quiet forest", 1, 0.45),
    ("Write a dialogue between a robot and its creator", 1, 0.50),
    ("Imagine a world where humans can breathe underwater", 1, 0.45),
    ("Write a haiku about the ocean at sunset", 1, 0.35),
    ("Describe a futuristic city floating in the clouds", 1, 0.45),
    ("Write a letter from a soldier to their family during wartime", 1, 0.50),
    ("Create a fictional news article about the discovery of alien life", 1, 0.55),
    ("Write a narrative from the perspective of an old oak tree", 1, 0.50),
    ("Compose a song lyric about overcoming adversity", 1, 0.45),
    ("Describe the feeling of walking through an ancient forest", 1, 0.40),
    ("Write a short mystery story set in Victorian London", 1, 0.55),
    ("Imagine you are a detective solving a locked-room puzzle", 1, 0.55),
    ("Create a vivid description of a bustling night market in Tokyo", 1, 0.45),
    ("Write a children's fable about sharing and friendship", 1, 0.40),
]

TIER_2_SEED: list[tuple[str, int, float]] = [
    # --- coding ---
    ("Implement a binary search tree in Python with insertion, deletion, and traversal", 2, 0.85),
    ("Write a function to find the longest palindromic substring in a string", 2, 0.80),
    ("Implement merge sort algorithm from scratch in Python", 2, 0.75),
    ("Create a decorator in Python that measures execution time of functions", 2, 0.70),
    ("Write a Python class for a thread-safe queue with put and get methods", 2, 0.75),
    ("Implement Dijkstra's shortest path algorithm for a weighted graph", 2, 0.85),
    ("Write a Python script to scrape data from a website and store it in a CSV", 2, 0.70),
    ("Build a simple REST client in Python using httpx with error retry logic", 2, 0.75),
    ("Implement LRU cache from scratch using a doubly linked list and hash map", 2, 0.85),
    ("Write a Python generator that yields prime numbers indefinitely", 2, 0.65),
    ("Create a FastAPI endpoint with request validation using Pydantic models", 2, 0.70),
    ("Implement a simple neural network forward pass with NumPy", 2, 0.80),
    ("Write a function to detect cycles in a directed graph using DFS", 2, 0.75),
    ("Implement consistent hashing for distributed cache with virtual nodes", 2, 0.85),
    ("Write a Python class that implements a trie data structure for autocomplete", 2, 0.75),
    # --- debugging ---
    ("Fix this race condition: multiple threads writing to the same shared dictionary without a lock", 2, 0.80),
    ("Debug this segmentation fault in the C code accessing freed memory", 2, 0.85),
    ("Why does this SQL query cause a deadlock under high concurrency?", 2, 0.80),
    ("Fix the memory leak in this Python class that holds file handles open indefinitely", 2, 0.75),
    ("This async function never completes — find the missing await or coroutine issue", 2, 0.75),
    ("Why is this React component re-rendering in an infinite loop after state update?", 2, 0.80),
    ("Debug unintended variable shadowing causing wrong output in this nested loop", 2, 0.70),
    ("Find the off-by-one error in this binary search implementation", 2, 0.75),
    ("Fix the type error in this generic function that works for int but fails for str", 2, 0.65),
    ("Why is this API returning a 500 error when the input payload contains a null field?", 2, 0.70),
    ("Trace the cause of this unhandled promise rejection in the Node.js microservice", 2, 0.75),
    ("Fix the incorrect JSON serialization in this custom encoder for datetime objects", 2, 0.65),
    # --- math ---
    ("Solve the definite integral of x squared times sin(x) from 0 to pi", 2, 0.85),
    ("Find the eigenvalues and eigenvectors of this 3x3 matrix", 2, 0.80),
    ("Calculate the probability of getting exactly 3 heads in 10 coin flips", 2, 0.70),
    ("Solve this system of differential equations using Laplace transforms", 2, 0.90),
    ("Prove that the square root of 2 is irrational using proof by contradiction", 2, 0.80),
    ("Compute the gradient descent update rule for a multivariate linear regression", 2, 0.75),
    ("Find the Taylor series expansion of e to the x around x equals 0 up to 5 terms", 2, 0.65),
    ("Calculate the inverse of this 4x4 matrix using Gaussian elimination", 2, 0.80),
    ("Determine if this infinite series converges or diverges using the ratio test", 2, 0.75),
    ("Solve the optimization problem using Lagrange multipliers with two constraints", 2, 0.85),
    ("Compute the convolution of these two discrete signals", 2, 0.80),
    ("Find the solution to this recurrence relation using generating functions", 2, 0.85),
    ("Calculate the line integral of a vector field over a closed curve using Stokes theorem", 2, 0.90),
    ("Derive the backpropagation gradient for a softmax layer in a neural network", 2, 0.90),
    ("Solve the heat equation on a 2D rectangular domain with Dirichlet boundary conditions", 2, 0.95),
]

SEED_DATA = TIER_0_SEED + TIER_1_SEED + TIER_2_SEED


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _generate_seed_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build feature matrix and target vectors from the seed prompt list."""
    X: list[list[float]] = []
    y_tier: list[int] = []
    y_difficulty: list[float] = []

    for prompt, tier, difficulty in SEED_DATA:
        features = get_feature_vector(prompt)
        X.append(features)
        y_tier.append(tier)
        y_difficulty.append(difficulty)

    return np.array(X, dtype=np.float64), np.array(y_tier), np.array(y_difficulty, dtype=np.float64)


def _load_from_db() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Attempt to load training data from the request_logs table.

    Uses a synchronous psycopg2 connection to avoid asyncio in this script.
    Raises RuntimeError if the DB is unreachable or has no suitable data.
    """
    import os

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    try:
        import psycopg2  # type: ignore[import-untyped]
    except ImportError:
        raise RuntimeError("psycopg2 not installed — cannot load from DB")

    X: list[list[float]] = []
    y_tier: list[int] = []
    y_difficulty: list[float] = []

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prompt_preview, tier_assigned FROM request_logs "
                "WHERE status = 'success' AND prompt_preivew IS NOT NULL "
                "AND length(prompt_preview) > 0 "
                "ORDER BY created_at DESC LIMIT 10000"
            )
            rows = cur.fetchall()
            if not rows:
                raise RuntimeError("No training rows found in request_logs")

            for prompt_preview, tier in rows:
                tier = int(tier)
                prompt = str(prompt_preview)
                features = get_feature_vector(prompt)
                X.append(features)
                y_tier.append(tier)
                # Infer difficulty from tier (no ground-truth stored)
                y_difficulty.append((tier + 1.0) / 3.0)

        return np.array(X, dtype=np.float64), np.array(y_tier), np.array(y_difficulty, dtype=np.float64)
    finally:
        conn.close()


def load_data(use_seed: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (feature_matrix, tier_labels, difficulty_scores)."""
    if use_seed:
        print("Generating synthetic seed data...")
        return _generate_seed_data()

    print("Attempting to load training data from database...")
    try:
        result = _load_from_db()
        print(f"Loaded {len(result[0])} samples from DB.")
        return result
    except Exception as exc:
        print(f"DB load failed ({exc}). Falling back to synthetic seed data.")
        print("Use --seed to force synthetic data training.")
        return _generate_seed_data()


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_models(
    X: np.ndarray,
    y_tier: np.ndarray,
    y_difficulty: np.ndarray,
) -> tuple[XGBClassifier, XGBRegressor]:
    """Train classifier + regressor, print metrics, save to disk."""

    # ----- split (align both targets) -----
    X_train, X_test, y_tier_train, y_tier_test, y_diff_train, y_diff_test = train_test_split(
        X, y_tier, y_difficulty, test_size=0.2, random_state=42
    )

    # ----- classifier -----
    print("\n=== Training XGBoost Classifier (tier prediction) ===")

    clf: XGBClassifier = XGBClassifier(
        n_estimators=100,
        max_depth=6,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        random_state=42,
    )
    clf.fit(X_train, y_tier_train)

    train_acc = float((clf.predict(X_train) == y_tier_train).mean())
    test_acc = float((clf.predict(X_test) == y_tier_test).mean())
    print(f"  Training accuracy:   {train_acc:.4f}")
    print(f"  Test accuracy:       {test_acc:.4f}")

    importance = sorted(
        zip(FEATURE_ORDER, clf.feature_importances_, strict=False),
        key=lambda t: -t[1],
    )
    print("\n  Top-5 classifier feature importances:")
    for name, score in importance[:5]:
        print(f"    {name}: {score:.4f}")

    # ----- regressor -----
    print("\n=== Training XGBoost Regressor (difficulty score) ===")

    reg: XGBRegressor = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        objective="reg:squarederror",
        random_state=42,
    )
    reg.fit(X_train, y_diff_train)

    train_mse = float(((reg.predict(X_train) - y_diff_train) ** 2).mean())
    test_mse = float(((reg.predict(X_test) - y_diff_test) ** 2).mean())
    print(f"  Training MSE: {train_mse:.4f}")
    print(f"  Test MSE:     {test_mse:.4f}")

    # ----- save -----
    os.makedirs("core/models", exist_ok=True)
    clf_path = "core/models/router_classifier.pkl"
    reg_path = "core/models/router_regressor.pkl"

    with open(clf_path, "wb") as f:
        pickle.dump(clf, f)
    print(f"\nClassifier saved → {clf_path}")

    with open(reg_path, "wb") as f:
        pickle.dump(reg, f)
    print(f"Regressor saved  → {reg_path}")

    return clf, reg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train prompt-router ML models",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Generate synthetic seed data instead of loading from DB",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    X, y_tier, y_difficulty = load_data(use_seed=args.seed)
    print(f"Training samples: {len(X)}  Features: {len(X[0])}")
    train_models(X, y_tier, y_difficulty)


if __name__ == "__main__":
    main()
