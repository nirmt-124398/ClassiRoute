import re
import textstat

PATTERNS = {
    "is_coding"    : r"\b(code|implement|function|class|algorithm|program|script|api|def |return)\b",
    "is_debugging" : r"\b(debug|error|traceback|exception|fix|bug|crash|not working|segfault)\b",
    "is_reasoning" : r"\b(explain|why|how does|analyze|compare|difference|evaluate)\b",
    "is_creative"  : r"\b(poem|story|creative|imagine|fiction|narrative|compose)\b",
    "is_multistep" : r"\b(design|architecture|plan|scalable|system|steps to|roadmap|build)\b",
    "is_math"      : r"\b(solve|calculate|equation|integral|derivative|probability|proof)\b",
    "is_summarize" : r"\b(summarize|summary|tldr|brief|overview|condense)\b",
    "is_simple_qa" : r"\b(what is|who is|when did|where is|capital of|define|meaning of)\b",
}

FEATURE_ORDER = [
    "char_count", "word_count", "sentence_count", "avg_word_length",
    "unique_word_ratio", "avg_sentence_len", "fk_grade", "has_code_block",
    "has_numbers", "question_count", "comma_count", "has_bullet",
    "has_constraints", "caps_ratio", "is_coding", "is_debugging",
    "is_reasoning", "is_creative", "is_multistep", "is_math",
    "is_summarize", "is_simple_qa", "complexity_score"
]

def extract_features(text: str) -> dict:
    if not text:
        text = " "
        
    text_lower = text.lower()
    
    char_count = len(text)
    word_count = textstat.lexicon_count(text, removepunct=True)
    sentence_count = textstat.sentence_count(text)
    
    word_count_safe = word_count if word_count > 0 else 1
    sentence_count_safe = sentence_count if sentence_count > 0 else 1
    
    words = re.findall(r'\b\w+\b', text_lower)
    unique_word_count = len(set(words))
    
    avg_word_length = char_count / word_count_safe
    unique_word_ratio = unique_word_count / word_count_safe
    avg_sentence_len = word_count / sentence_count_safe
    fk_grade = textstat.flesch_kincaid_grade(text)
    
    has_code_block = 1.0 if "```" in text else 0.0
    has_numbers = 1.0 if bool(re.search(r'\d', text)) else 0.0
    question_count = float(text.count("?"))
    comma_count = float(text.count(","))
    
    has_bullet = 1.0 if bool(re.search(r'(?m)^[-*]\s', text)) else 0.0
    has_constraints = 1.0 if bool(re.search(r'\b(must|require|limit|only|exactly)\b', text_lower)) else 0.0
    
    caps_count = len(re.findall(r'[A-Z]', text))
    caps_ratio = caps_count / char_count if char_count > 0 else 0.0
    
    features = {
        "char_count": float(char_count),
        "word_count": float(word_count),
        "sentence_count": float(sentence_count),
        "avg_word_length": float(avg_word_length),
        "unique_word_ratio": float(unique_word_ratio),
        "avg_sentence_len": float(avg_sentence_len),
        "fk_grade": float(fk_grade),
        "has_code_block": has_code_block,
        "has_numbers": has_numbers,
        "question_count": question_count,
        "comma_count": comma_count,
        "has_bullet": has_bullet,
        "has_constraints": has_constraints,
        "caps_ratio": float(caps_ratio)
    }
    
    # Pattern matching
    for key, pattern in PATTERNS.items():
        features[key] = 1.0 if bool(re.search(pattern, text_lower)) else 0.0
        
    # Heuristic complexity score
    complexity_score = 0.0
    complexity_score += features["is_coding"] * 2.0
    complexity_score += features["is_debugging"] * 2.0
    complexity_score += features["is_multistep"] * 2.5
    complexity_score += features["is_reasoning"] * 2.0
    complexity_score += features["is_math"] * 1.5
    complexity_score += features["has_code_block"] * 1.5
    complexity_score += features["has_constraints"] * 1.0
    
    # Sentence and word length add to complexity somewhat
    if fk_grade > 12:
        complexity_score += 1.0
        
    features["complexity_score"] = float(complexity_score)
    
    return features


def get_feature_vector(text: str) -> list[float]:
    feats = extract_features(text)
    return [feats[k] for k in FEATURE_ORDER]
