"""
Evaluation endpoint for internal testing and tier routing analysis.

This endpoint exposes the routing decision tree without making API calls
to AI providers. Use it to:
- Understand why a prompt was assigned to a specific tier
- Evaluate tier assignment accuracy
- Compare routing decisions across different prompts
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth.dependencies import get_virtual_key
from core.feature_extractor import extract_features, FEATURE_ORDER
from core.router import route_prompt, CLASSIFIER, REGRESSOR, TIER_NAMES, CONFIDENCE_THRESHOLD
from db.models import VirtualKey

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal")


class EvaluateRequest(BaseModel):
    prompt: str
    show_counterfactuals: bool = True
    show_feature_breakdown: bool = True
    show_all_tier_recommendations: bool = False


class FeatureContribution(BaseModel):
    feature_name: str
    value: float
    contribution: str
    impact: str  # "high", "medium", "low", "none"


class TierAnalysis(BaseModel):
    tier: int
    tier_name: str
    suitable: bool
    confidence: float
    reasoning: List[str]


class EvaluateResponse(BaseModel):
    prompt: str
    assigned_tier: int
    assigned_tier_name: str
    confidence: float
    difficulty_score: float
    decision_method: str  # "classifier" or "heuristic"
    was_upgraded: bool
    
    # Feature analysis
    features: Dict[str, float]
    complexity_score: float
    feature_contributions: List[FeatureContribution]
    
    # Reasoning
    why_this_tier: List[str]
    why_not_other_tiers: Dict[str, List[str]]
    
    # Counterfactuals
    counterfactuals: Optional[Dict[str, Dict]] = None
    
    # All tiers (if requested)
    all_tier_analysis: Optional[List[TierAnalysis]] = None
    
    # Performance
    feature_extraction_time_ms: float


def _generate_reasoning(features: dict, routing: dict) -> List[str]:
    """Generate human-readable reasoning for the tier assignment."""
    reasons = []
    
    # Complexity-based reasoning
    complexity = features.get("complexity_score", 0)
    if complexity < 2.0:
        reasons.append(f"Low complexity score ({complexity:.2f} < 2.0) indicates a simple task")
    elif complexity < 4.0:
        reasons.append(f"Moderate complexity score ({complexity:.2f}) indicates mid-level difficulty")
    else:
        reasons.append(f"High complexity score ({complexity:.2f} >= 4.0) indicates a challenging task")
    
    # Pattern-based reasoning
    active_patterns = []
    pattern_weights = {
        "is_coding": "Contains coding keywords (implement, function, algorithm)",
        "is_debugging": "Contains debugging keywords (debug, error, fix, bug)",
        "is_multistep": "Contains architecture/design keywords (design, system, architecture, build)",
        "is_reasoning": "Requires reasoning/explanation (explain, why, analyze, compare)",
        "is_math": "Contains mathematical terms (solve, equation, probability, proof)",
        "is_creative": "Creative writing task (poem, story, fiction)",
        "is_summarize": "Summarization task (summarize, summary, tldr)",
        "is_simple_qa": "Simple factual question (what is, who is, define)",
    }
    
    for pattern, description in pattern_weights.items():
        if features.get(pattern, 0) > 0:
            active_patterns.append(description)
    
    if active_patterns:
        reasons.append("Detected patterns: " + "; ".join(active_patterns))
    
    # Structural reasoning
    if features.get("has_code_block", 0) > 0:
        reasons.append("Contains code blocks (```), indicating code-related task")
    
    if features.get("has_constraints", 0) > 0:
        reasons.append("Contains constraint keywords (must, require, limit), indicating specific requirements")
    
    if features.get("fk_grade", 0) > 12:
        reasons.append(f"High reading grade level ({features['fk_grade']:.1f}) suggests complex content")
    
    if features.get("word_count", 0) > 100:
        reasons.append(f"Long prompt ({features['word_count']:.0f} words) suggests detailed requirements")
    
    # Decision method
    if routing.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
        reasons.append(f"ML classifier confident (confidence={routing['confidence']:.2f} >= {CONFIDENCE_THRESHOLD}) in {routing['tier_name']} tier")
    else:
        reasons.append(f"Low confidence ({routing['confidence']:.2f} < {CONFIDENCE_THRESHOLD}), upgraded to stronger model")
    
    return reasons


def _generate_counterfactuals(features: dict, routing: dict) -> Dict[str, Dict]:
    """Generate what-if scenarios for other tiers."""
    complexity = features.get("complexity_score", 0)
    current_tier = routing["tier"]
    
    counterfactuals = {}
    
    for tier_num, tier_name in TIER_NAMES.items():
        if tier_num == current_tier:
            continue
            
        analysis = {
            "tier": tier_num,
            "tier_name": tier_name,
            "would_choose": False,
            "confidence_if_chosen": None,
            "why_not": [],
            "risk_assessment": "",
        }
        
        # Why this tier wasn't chosen
        if tier_num < current_tier:
            # Lower tier - would underperform
            if complexity >= 4.0:
                analysis["why_not"].append(f"Complexity score {complexity:.2f} exceeds threshold for {tier_name} (>= 4.0)")
            
            if features.get("is_coding", 0) > 0 and tier_num < 2:
                analysis["why_not"].append("Coding tasks should use strongest model for accuracy")
            
            if features.get("is_debugging", 0) > 0 and tier_num < 2:
                analysis["why_not"].append("Debugging tasks require strong model to avoid errors")
            
            if features.get("is_multistep", 0) > 0 and tier_num < 2:
                analysis["why_not"].append("Multi-step design tasks need strong model")
                
            analysis["risk_assessment"] = "Risk: Model may provide incomplete or incorrect responses"
            analysis["cost_impact"] = f"Would save ~{(current_tier - tier_num) * 50}% API cost"
            
        else:
            # Higher tier - overkill but safe
            if complexity < 2.0:
                analysis["why_not"].append(f"Complexity score {complexity:.2f} is too low for {tier_name}")
            
            if features.get("is_simple_qa", 0) > 0:
                analysis["why_not"].append("Simple factual queries don't need expensive model")
            
            analysis["risk_assessment"] = "Would work fine but unnecessary cost"
            analysis["cost_impact"] = f"Would cost ~{(tier_num - current_tier) * 50}% more API cost"
        
        if not analysis["why_not"]:
            analysis["why_not"].append("Tier difference based on ML model confidence threshold")
        
        counterfactuals[f"tier_{tier_num}_{tier_name}"] = analysis
    
    return counterfactuals


def _get_feature_contributions(features: dict) -> List[FeatureContribution]:
    """Calculate how much each feature contributed to the complexity score."""
    contributions = []
    
    # Complexity score components
    complexity_weights = {
        "is_coding": 2.0,
        "is_debugging": 2.0,
        "is_multistep": 2.5,
        "is_reasoning": 2.0,
        "is_math": 1.5,
        "has_code_block": 1.5,
        "has_constraints": 1.0,
    }
    
    fk_grade = features.get("fk_grade", 0)
    
    for feature_name in FEATURE_ORDER:
        value = features.get(feature_name, 0)
        
        if feature_name in complexity_weights:
            weight = complexity_weights[feature_name]
            contribution = value * weight
            impact = "high" if contribution >= 2.0 else "medium" if contribution >= 1.0 else "low" if contribution > 0 else "none"
            contribution_str = f"+{contribution:.1f} to complexity score (weight={weight})"
        elif feature_name == "fk_grade":
            contribution = 1.0 if fk_grade > 12 else 0.0
            impact = "medium" if contribution > 0 else "none"
            contribution_str = f"Reading grade {fk_grade:.1f} {'exceeds' if contribution > 0 else 'below'} threshold 12"
        elif feature_name == "complexity_score":
            contribution_str = f"Total complexity score"
            impact = "high"
        else:
            contribution_str = "Structural feature (no direct complexity impact)"
            impact = "none"
        
        contributions.append(FeatureContribution(
            feature_name=feature_name,
            value=float(value),
            contribution=contribution_str,
            impact=impact
        ))
    
    return contributions


def _analyze_all_tiers(features: dict) -> List[TierAnalysis]:
    """Analyze suitability of each tier for this prompt."""
    complexity = features.get("complexity_score", 0)
    
    analyses = []
    for tier_num, tier_name in TIER_NAMES.items():
        suitable = False
        reasoning = []
        confidence = 0.0
        
        if tier_num == 0:
            # Weak tier suitable for simple tasks
            if complexity < 2.0 and not any([
                features.get("is_coding", 0) > 0,
                features.get("is_debugging", 0) > 0,
                features.get("is_multistep", 0) > 0,
            ]):
                suitable = True
                confidence = 0.8
                reasoning.append("Low complexity with no challenging patterns")
            else:
                reasoning.append(f"Complexity {complexity:.2f} too high for weak model")
                if features.get("is_coding", 0) > 0:
                    reasoning.append("Coding tasks need stronger model")
        
        elif tier_num == 1:
            # Mid tier for moderate tasks
            if 2.0 <= complexity < 4.0 or (
                features.get("is_reasoning", 0) > 0 and 
                not features.get("is_coding", 0) > 0 and
                not features.get("is_multistep", 0) > 0
            ):
                suitable = True
                confidence = 0.7
                reasoning.append("Moderate complexity - mid model sufficient")
            else:
                reasoning.append(f"Complexity {complexity:.2f} outside mid-tier range [2.0, 4.0)")
        
        else:  # tier 2
            # Strong tier for complex tasks
            if complexity >= 4.0 or any([
                features.get("is_coding", 0) > 0,
                features.get("is_debugging", 0) > 0,
                features.get("is_multistep", 0) > 0,
            ]):
                suitable = True
                confidence = 0.9
                reasoning.append("High complexity or challenging patterns detected")
            else:
                reasoning.append("May be overkill for this complexity level")
        
        analyses.append(TierAnalysis(
            tier=tier_num,
            tier_name=tier_name,
            suitable=suitable,
            confidence=confidence,
            reasoning=reasoning
        ))
    
    return analyses


@router.post("/evaluate-route", response_model=EvaluateResponse)
async def evaluate_route(
    request: EvaluateRequest,
    virtual_key: VirtualKey = Depends(get_virtual_key),
):
    """
    Evaluate tier routing decision for a prompt WITHOUT making API calls.
    
    Returns:
    - The routing decision and features extracted
    - Why the prompt was assigned to this tier
    - Why other tiers were rejected
    - Counterfactual analysis (what if it went to a different tier?)  
    - Feature contributions to the complexity score
    """
    import time
    
    start = time.time()
    
    # Extract features - this is fast, no API calls
    features = extract_features(request.prompt)
    routing = route_prompt(request.prompt)
    
    extraction_time = (time.time() - start) * 1000
    
    # Determine decision method
    if CLASSIFIER is not None:
        decision_method = "classifier"
    else:
        decision_method = "heuristic"
    
    # Generate reasoning
    why_this_tier = _generate_reasoning(features, routing)
    
    # Generate why not other tiers
    why_not = {}
    for tier_num, tier_name in TIER_NAMES.items():
        if tier_num != routing["tier"]:
            why_not[tier_name] = [f"Tier {tier_name} not chosen for this prompt"]
    
    # Build response
    response = EvaluateResponse(
        prompt=request.prompt,
        assigned_tier=routing["tier"],
        assigned_tier_name=routing["tier_name"],
        confidence=routing["confidence"],
        difficulty_score=routing["difficulty_score"],
        decision_method=decision_method,
        was_upgraded=routing.get("upgraded", False),
        features={k: float(v) for k, v in features.items()},
        complexity_score=features.get("complexity_score", 0.0),
        feature_contributions=_get_feature_contributions(features),
        why_this_tier=why_this_tier,
        why_not_other_tiers=why_not,
        counterfactuals=_generate_counterfactuals(features, routing) if request.show_counterfactuals else None,
        all_tier_analysis=_analyze_all_tiers(features) if request.show_all_tier_recommendations else None,
        feature_extraction_time_ms=round(extraction_time, 3)
    )
    
    logger.info(
        "evaluate-route: prompt_length=%d tier=%s confidence=%.2f time=%.3fms",
        len(request.prompt), routing["tier_name"], routing["confidence"], extraction_time
    )
    
    return response


@router.get("/evaluate-sample")
async def evaluate_sample_prompts():
    """Return pre-defined sample prompts with expected tier assignments for evaluation."""
    samples = [
        {
            "prompt": "What is the capital of France?",
            "expected_tier": 0,
            "description": "Simple factual question"
        },
        {
            "prompt": "Explain the difference between REST and GraphQL.",
            "expected_tier": 1,
            "description": "Comparative explanation"
        },
        {
            "prompt": "Design and implement a distributed caching system using Redis with eventual consistency.",
            "expected_tier": 2,
            "description": "System design + implementation"
        },
        {
            "prompt": "Write a Python function to calculate the Fibonacci sequence.",
            "expected_tier": 2,
            "description": "Coding task"
        },
        {
            "prompt": "Summarize the key points of this article about climate change.",
            "expected_tier": 0,
            "description": "Summarization"
        },
        {
            "prompt": "Debug this error: TypeError: Cannot read property 'map' of undefined in React component.",
            "expected_tier": 2,
            "description": "Debugging task"
        },
        {
            "prompt": "Write a creative short story about a robot learning to paint.",
            "expected_tier": 1,
            "description": "Creative writing"
        },
        {
            "prompt": "Solve the integral of x^2 * e^x dx.",
            "expected_tier": 2,
            "description": "Mathematical problem"
        }
    ]
    
    return {
        "total_samples": len(samples),
        "samples": samples,
        "usage": "Send any prompt to POST /internal/evaluate-route to see routing analysis"
    }
