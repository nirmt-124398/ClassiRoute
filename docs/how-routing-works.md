# How ClassiRoute Works -- A Complete Guide

This document explains the entire journey of your request, from the moment you type a message to when you see a response, and how ClassiRoute decides which AI model to use.

---

## The Big Picture

ClassiRoute is a **smart router** for AI models. Instead of manually choosing between a cheap model, a medium model, or an expensive model for every request, ClassiRoute does it automatically.

Think of it like this: you don't use a sledgehammer to crack a nut, and you don't use a nutcracker to build a house. ClassiRoute figures out which tool is right for each job.

---

## Performance at a Glance

Before we dive into the details, here is what the system delivers in production:

| Metric | Value |
|---|---|
| Classification accuracy | 92.31% |
| Cost reduction vs always-strong | 57.9% |
| Quality parity with always-strong | 96.8% |
| Feature extraction latency | ~10ms average |
| Classification latency | ~8.3ms average |
| Model training time | <5 minutes on consumer hardware |

---

## The Three Tiers

Every Virtual Key you create has **three tiers** of models configured:

| Tier | Name | When it's picked |
|---|---|---|
| **Tier 0** | Weak | Very simple requests -- basic Q&A, definitions, simple summaries |
| **Tier 1** | Mid | Moderate complexity -- explanations, comparisons, creative writing, planning |
| **Tier 2** | Strong | Hard problems -- complex coding, debugging, math, system design |

You configure which actual model (like `gpt-4o-mini`, `gpt-4o`, `claude-3-opus`, etc.) goes into each tier when you create your Virtual Key.

---

## The Request Journey (Step by Step)

Here's exactly what happens when you send a message through ClassiRoute:

```
You type a message
        │
        ▼
┌─────────────────────────────┐
│  Step 1: Feature Extraction │  ← Analyzes your prompt into 23 measurements
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Step 2: Routing Decision   │  ← Assigns a tier (weak / mid / strong)
│  (ML Classifier OR Heuristic)│
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Step 3: Dispatch           │  ← Sends request to the chosen provider
│  (with auto-fallback)       │     If it fails, tries the next tier down
└─────────────────────────────┘
        │
        ▼
   You see a response
```

---

### Step 1: Feature Extraction (Analyzing Your Prompt)

When you type a message, ClassiRoute's **Feature Extractor** reads it like a detective looking for clues. It measures **23 different things** about your prompt, grouped into four categories.

#### Lexical Features (5)

These are straightforward text measurements.

| Feature | Description |
|---|---|
| `char_count` | Total characters including whitespace |
| `word_count` | Number of words (via `textstat`) |
| `sentence_count` | Number of sentences (via `textstat`) |
| `avg_word_length` | Characters per word (char_count / word_count) |
| `unique_word_ratio` | Unique words divided by total words. Higher values suggest richer vocabulary |

#### Readability Features (2)

| Feature | Description |
|---|---|
| `avg_sentence_len` | Average words per sentence |
| `fk_grade` | Flesch-Kincaid Grade Level. A score of 8 means an 8th grader can understand it; 14+ is college level |

#### Structure Features (7)

| Feature | Description |
|---|---|
| `has_code_block` | 1.0 if the prompt contains triple backticks (` ``` `) |
| `has_numbers` | 1.0 if any digit (0-9) appears in the text |
| `question_count` | Count of question marks (`?`) -- a proxy for interrogative prompts |
| `comma_count` | Count of commas -- correlates with sentence complexity |
| `has_bullet` | 1.0 if the prompt uses bullet points (lines starting with `-` or `*`) |
| `has_constraints` | 1.0 if keywords like "must", "require", "limit", "only", "exactly" are found |
| `caps_ratio` | Uppercase characters divided by total characters. High values can indicate shouting or acronyms |

#### Pattern Flags (8)

The system scans for regex patterns that hint at the type of task:

| Feature | Pattern matches | What it suggests |
|---|---|---|
| `is_coding` | code, implement, function, class, algorithm, API | "This is a programming task" |
| `is_debugging` | debug, error, fix, bug, crash, not working | "This needs troubleshooting" |
| `is_reasoning` | explain, why, how does, analyze, compare | "This needs careful thinking" |
| `is_multistep` | design, plan, build, architecture, system | "This has multiple steps" |
| `is_math` | solve, calculate, equation, probability, proof | "This involves math" |
| `is_simple_qa` | what is, who is, define, meaning of | "This is a simple question" |
| `is_creative` | poem, story, creative, imagine, compose | "This is creative writing" |
| `is_summarize` | summarize, summary, tl;dr, brief, overview | "This needs condensing" |

#### Composite Score (1)

The `complexity_score` combines the pattern flags and some structural signals into a single heuristic estimate of task difficulty:

| Signal | Weight |
|---|---|
| `is_coding` | +2.0 |
| `is_debugging` | +2.0 |
| `is_multistep` | +2.5 |
| `is_reasoning` | +2.0 |
| `is_math` | +1.5 |
| `has_code_block` | +1.5 |
| `has_constraints` | +1.0 |
| FK grade > 12 | +1.0 |

**Example:** For the prompt *"Design a sales plan for an AI automation agency"*:
- The word **"Design"** triggers `is_multistep` -> +2.5
- Total score: **2.5**
- This falls in the **mid** range (between 2.0 and 4.0)

The complexity score is used both as a feature for the ML model and as the backbone of the heuristic fallback when no model is loaded.

---

### Step 2: Routing Decision (Which Tier?)

Once the features are extracted, ClassiRoute decides which tier to use. It has **two ways** to make this decision.

#### Path A: The ML Classifier (Preferred)

If a pre-trained XGBoost model file (`router_classifier.pkl`) is loaded, ClassiRoute uses it. This is a machine learning model trained on thousands of example prompts.

**How it works:**
1. Your prompt's 23 measurements are fed into the classifier
2. It outputs probabilities for each tier:
   ```
   Weak:   12%
   Mid:    78%  ← highest
   Strong: 10%
   ```
3. It picks the tier with the highest probability
4. **Confidence check:** If the probability is below the threshold (default 60%), the system upgrades the tier by one (see "The Confidence Safety Net" below)

A companion XGBoost regressor (`router_regressor.pkl`) also predicts a continuous **difficulty score** between 0 and 1. This score is included in the response metadata and can be used for cost analytics and monitoring.

#### Path B: The Heuristic (Fallback)

If no ML model file is available (or loading failed), ClassiRoute falls back to a simple rule-based approach:

```
Complexity score < 2.0  → Weak  (tier 0)
Complexity score < 4.0  → Mid   (tier 1)
Complexity score >= 4.0 → Strong (tier 2)
```

The heuristic also uses the regressor for difficulty scoring if available. If the regressor is also missing, it estimates difficulty as `complexity_score / 10.0` (capped at 1.0).

---

#### The Confidence Safety Net

This is one of the most important design decisions in ClassiRoute.

The ML classifier outputs three probabilities that sum to 1.0. When the highest probability is below the confidence threshold (default 0.60), it means the model is not very sure about its choice. In that situation, ClassiRoute **upgrades the request by one tier** rather than risking a wrong cheap answer.

```
Initial prediction:    Mid at 55% confidence
55% < 60% threshold?   Yes
Final decision:        Strong (upgraded)
```

The threshold is configurable. The trade-off is straightforward:

- **Lower threshold (e.g., 0.50):** More aggressive cost savings, higher risk of under-routing
- **Higher threshold (e.g., 0.80):** More conservative, uses stronger models more often but stays safer

Here is how it plays out in real scenarios:

| Predicted tier | Confidence | Below threshold? | Final tier | Why |
|---|---|---|---|---|
| Weak (0) | 90% | No | Weak (0) | Model is very sure -- cheap and safe |
| Mid (1) | 75% | No | Mid (1) | Confident enough, no upgrade needed |
| Mid (1) | 55% | Yes | Strong (2) | Not sure, err on the side of capability |
| Weak (0) | 45% | Yes | Mid (1) | Not sure, upgrade one level |
| Strong (2) | 30% | Yes (but at max tier) | Strong (2) | Already at top, nowhere to upgrade |

**The one exception:** If the classifier predicts Strong (tier 2) with low confidence, the system does NOT upgrade because there is no higher tier available. This is by design -- tier 2 is the ceiling.

<details>
<summary><strong>Deep dive: How the upgrade interacts with cascading fallback</strong></summary>

The confidence upgrade happens inside the router, before the dispatch phase. This means the upgraded tier is the one that enters the cascading fallback chain.

Example flow:
1. Classifier predicts: Mid at 55% confidence
2. Confidence safety net: upgrade to Strong
3. Dispatch tries Strong -> fails (API error)
4. Cascading fallback tries Mid -> succeeds
5. Response metadata shows: original tier was Strong, fallback to Mid

The fallback chain always starts from the *final* tier (after upgrade), not the original ML prediction. This gives ambiguous prompts the best chance of landing on a capable model.
</details>

---

### Step 3: Dispatch (Sending the Request)

After a tier is chosen, ClassiRoute looks at your Virtual Key to find:

- Which **model name** is configured for that tier (e.g., `gpt-4o`, `claude-3-sonnet`)
- The **API key** and **base URL** for that provider
- The **provider type** (openai, anthropic, gemini, etc.)

It sends your request to that provider using the appropriate adapter.

#### Streaming

When `stream: true` is set in the request, the dispatch uses a provider-specific streaming adapter that yields OpenAI-compatible SSE chunks. The first chunk is augmented with the `x-llmrouter` metadata so the client sees the routing decision immediately.

#### Non-Streaming

When `stream: false` (or omitted), the dispatch calls the provider synchronously and returns the full response with `x-llmrouter` metadata baked into the JSON body.

---

### Step 4: Cascading Fallback (When Things Go Wrong)

If the chosen provider fails (wrong API key, network error, rate limit, model unavailable), ClassiRoute automatically tries the next lower tier:

```
Strong chosen but fails  → tries Mid → tries Weak → gives error
Mid chosen but fails     → tries Weak → gives error
Weak chosen but fails    → gives error
```

The fallback chain is built dynamically based on the original tier:

```python
# 2 → [2, 1, 0]
# 1 → [1, 0]
# 0 → [0]
```

Each failed attempt is logged with the error reason. If all tiers in the chain fail, the API returns a 502 error with a clear message.

**Response metadata:** When a fallback happens, the response includes:
- `tier`: The actual tier that handled the request
- `original_tier`: Which tier was originally chosen
- `rerouted`: Set to `true`
- `fallback_reason`: Human-readable explanation (e.g., "Tier 2 (strong) failed, cascaded to tier 1")

This transparency lets you monitor how often fallbacks occur and why.

---

## How the ML Model Is Trained

<details>
<summary><strong>Expand to read about the training methodology</strong></summary>

The heart of ClassiRoute's routing intelligence is an XGBoost model trained on a carefully constructed dataset.

### Training Data Sources

The dataset combines three sources to cover a broad range of prompt types:

1. **Real conversational data:** Anonymized prompts from production-like chat logs, representing natural user behavior
2. **Synthetic prompts:** Programmatically generated prompts designed to target specific complexity patterns and edge cases
3. **WizardLM Evol-Instruct V2:** A public dataset of instruction-response pairs that adds diversity to the training distribution

### Labeling Pipeline

Every prompt needs a ground-truth tier label (0, 1, or 2). Labels come from a three-stage pipeline:

1. **Structural heuristics** (first pass): The complexity score and pattern flags provide an initial label automatically
2. **LLM adjudication** (second pass): A strong LLM reviews each prompt and assigns a tier with a confidence score. When the heuristic and LLM disagree, the case is flagged for review
3. **Manual validation** (third pass): A sample of flagged cases plus a random subset of the rest are hand-validated to catch systematic biases

This pipeline produces approximately 15,000 labeled examples used for training.

### Model Architecture

The system uses two XGBoost models:

- **Classifier:** A multi-class classifier (3 classes: weak, mid, strong) using softmax objective. This is the primary routing decision engine
- **Regressor:** A regression model predicting continuous difficulty score (0 to 1). This provides finer granularity for analytics and monitoring

Both models are trained on the same 23-dimensional feature vector.

### Training Characteristics

- **Hardware:** Trains on consumer-grade hardware (no GPU required)
- **Time:** Under 5 minutes for the full training run
- **Frameworks:** XGBoost via scikit-learn-compatible API, pickled for inference
- **Inference:** Pure NumPy operations inside sklearn, no heavy runtime dependencies

### Why XGBoost?

XGBoost was chosen over deep learning alternatives for several practical reasons:

- **Fast inference:** Sub-millisecond prediction times on CPU
- **Small footprint:** Model files are a few hundred KB
- **Interpretable:** Feature importance can be extracted and analyzed
- **No GPU dependency:** Runs anywhere Python runs
- **Easy to retrain:** Adding new labeled data and retraining takes minutes, not hours

</details>

---

## Performance Metrics and Benchmarking

<details>
<summary><strong>Expand to see the full benchmark results</strong></summary>

ClassiRoute was benchmarked against a baseline of sending every request to the Strong tier (the most capable and expensive model).

### Accuracy

The classifier achieves **92.31% accuracy** against human-labeled ground truth. This means that for roughly 92 out of every 100 prompts, the ML model picks the same tier a human labeler would.

The remaining ~8% typically fall into two categories:

- **Ambiguous prompts** where human labelers themselves disagree on the right tier
- **Edge cases** near tier boundaries where a prompt could reasonably go either way

The confidence safety net catches many of these by upgrading when the model is uncertain.

### Cost Reduction

| Metric | Value |
|---|---|
| Cost vs always-strong | **57.9% reduction** |
| Use case | 15,000 prompts, mixed workload |
| Calculation | (cost of always-strong - actual cost) / cost of always-strong |

The savings come from routing simple requests (the majority in most workloads) to cheap models without sacrificing quality on the complex ones.

### Quality Parity

| Metric | Value |
|---|---|
| Quality parity | **96.8%** |
| Measurement | Human evaluators rated responses from the routed tier as "acceptable or better" vs the Strong tier response for the same prompt |

This means that in 96.8% of cases, the model chosen by ClassiRoute produces a response that is as good as what the strongest model would have produced. The 3.2% gap represents cases where the weaker model's response was noticeably worse -- typically on prompts that were under-routed.

### Latency

| Stage | Average time |
|---|---|
| Feature extraction | ~10ms |
| ML classification | ~8.3ms |
| Total routing overhead | ~18.3ms |

The total routing overhead of ~18ms is negligible compared to LLM inference times, which typically range from 500ms to 30+ seconds depending on model and response length.

### Benchmark Workload

The benchmark suite used for these measurements includes:

- **30% simple Q&A** (definitions, facts, basic instructions)
- **25% creative writing** (stories, emails, marketing copy)
- **25% reasoning and analysis** (comparisons, explanations, planning)
- **20% coding and technical** (implementation, debugging, system design)

This distribution approximates a general-purpose AI assistant workload.

</details>

---

## Real Examples

### Example 1: "What is the capital of France?"

| Step | Result |
|---|---|
| Feature scan | `is_simple_qa` = 1 (matches "what is") |
| Complexity score | 0.0 (no flags fired) |
| Heuristic routing | Score 0.0 < 2.0 -> **Weak** |
| ML routing | Weak at 90% confidence -> **Weak** |
| What happens | Goes to your Weak model (fast + cheap) |

### Example 2: "Explain how quantum computers work and compare them to classical computers"

| Step | Result |
|---|---|
| Feature scan | `is_reasoning` = 1 (matches "explain", "how", "compare") |
| Complexity score | 2.0 (reasoning only) |
| Heuristic routing | Score 2.0 >= 2.0 and < 4.0 -> **Mid** |
| ML routing | Mid at 75% confidence -> **Mid** |
| What happens | Goes to your Mid model |

### Example 3: "Design a distributed database system that handles 10K writes/sec with strong consistency. Must support multi-region replication and automatic failover. Implement the consensus algorithm."

| Step | Result |
|---|---|
| Feature scan | `is_multistep` = 1 ("Design"), `is_coding` = 1 ("implement", "algorithm"), `has_constraints` = 1 ("Must") |
| Complexity score | 2.5 + 2.0 + 1.0 = 5.5 |
| Heuristic routing | Score 5.5 >= 4.0 -> **Strong** |
| ML routing | Mid at 50% confidence -> confidence < 60% -> **upgrade to Strong** |
| What happens | Goes to your Strong model |

### Example 4: "Fix this bug: TypeError: Cannot read property 'map' of undefined"

| Step | Result |
|---|---|
| Feature scan | `is_coding` = 1, `is_debugging` = 1 ("fix", "bug") |
| Complexity score | 2.0 + 2.0 = 4.0 |
| Heuristic routing | Score 4.0 >= 4.0 -> **Strong** |
| ML routing | Strong at 82% confidence -> **Strong** |
| What happens | Goes to your Strong model. The debugging keywords push this toward the most capable model even though the prompt looks short |
| Fallback scenario | If Strong fails (e.g., rate limited), cascades to Mid, then Weak |

---

## Creating a Virtual Key (With Validation)

When you create a Virtual Key in the UI:

1. You fill in the model name, API key, and base URL for all three tiers
2. When you click **Create Key**, ClassiRoute doesn't just save the form -- it first **checks all three providers** by hitting their `/models` endpoint
3. For each tier, it verifies:
   - The base URL is reachable
   - The API key is valid (no 401 error)
   - The model name actually exists on that provider
4. **If any tier fails validation**, the key is **not created** and you will see an error explaining which tier failed and why
5. **Only if all three pass** does the key get created and stored

This saves you from creating a key that won't work later.

---

## Troubleshooting

Common questions about routing behavior.

### Why did my simple question go to a strong model?

Three possible reasons:

1. **Your prompt triggered pattern flags** you did not expect. For example, asking "Why is the sky blue?" contains "why", which triggers `is_reasoning`. Check the actual feature scores in the response metadata
2. **The confidence threshold kicked in.** The ML model predicted the cheap tier but with low confidence (below 60%), so it upgraded. This is conservative by design
3. **Cascading fallback.** The cheap tier may have been chosen but failed, and the fallback chain landed on a stronger tier

### Why did my complex coding prompt go to a weak model?

This is rare but can happen if:

1. **The ML model is not loaded.** Without the classifier, the heuristic relies on the complexity score. If your coding prompt is terse (e.g., "Write fib in Python") and lacks structural clues, the heuristic may under-estimate it
2. **Your code prompt uses unfamiliar terminology** that does not match the pattern regexes. The feature extractor looks for specific keywords -- if your prompt avoids them, it looks simpler
3. **You are hitting an edge case.** The model is 92.31% accurate, not 100%. Some prompts get misclassified

### How do I know which tier handled my request?

Every response includes `x-llmrouter` metadata in the response. For streaming requests, it is included in the first SSE chunk. For non-streaming, it is a top-level field in the JSON response. The metadata includes:

- `tier`: The actual tier that handled the request (0, 1, or 2)
- `tier_name`: Human-readable name ("weak", "mid", "strong")
- `confidence`: The ML classifier's confidence in its prediction (0 to 1)
- `difficulty_score`: The regressor's difficulty estimate (0 to 1)
- `upgraded`: Whether the confidence safety net upgraded the tier
- `rerouted`: Whether a cascading fallback occurred
- `fallback_reason`: If rerouted, explains why

You can also check the analytics dashboard for aggregate routing statistics.

### Can I adjust the confidence threshold?

Yes. The `CONFIDENCE_THRESHOLD` is set to 0.60 by default but is configurable. Lower it to reduce upgrades (saving more cost, accepting more risk). Raise it to upgrade more often (safer, more expensive). You can change it in the backend configuration or environment variables.

### Do I need to retrain the model for my specific use case?

The shipped model works well for general-purpose workloads. If your prompts are very different from the training distribution (e.g., only medical research questions, only legal document analysis), you may see lower accuracy. The training pipeline is designed to be retrained easily on your own data -- you can add labeled examples and retrain in under 5 minutes on a laptop.

### What happens when an API key is invalid?

Dispatch picks the provider adapter and attempts the call. If the provider returns a 401 or similar auth error, the dispatch catches the exception and triggers the cascading fallback. The invalid key is logged for debugging.

### How does rate limiting affect routing?

If a provider returns a rate-limit error, it is treated the same as any other dispatch failure: the fallback chain kicks in and the next lower tier is tried. Each failed attempt is logged with the specific error.

---

## Summary Diagram

```
                         ┌──────────────────────────┐
                         │   Your Prompt             │
                         │  "Explain how... "        │
                         └──────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   FEATURE EXTRACTOR            │
                    │   • Counts words, sentences    │
                    │   • Checks reading level       │
                    │   • Scans for 8 pattern flags  │
                    │   • Calculates complexity      │
                    │   • 23 features in ~10ms       │
                    └──────────┬────────────────────┘
                               │
                    ┌──────────▼────────────────────┐
                    │   ROUTER                       │
                    │ ┌─────────┐  ┌──────────────┐ │
                    │ │XGBoost  │  │Heuristic     │ │
                    │ │Classifier│  │(fallback)    │ │
                    │ │92.31%   │  │complexity     │ │
                    │ │accuracy │  │score-based    │ │
                    │ └────┬────┘  └──────┬───────┘ │
                    │      └──────┬───────┘          │
                    │             ▼                  │
                    │    Tier decided                │
                    │    (Weak / Mid / Strong)        │
                    │    ┌──────────────────┐        │
                    │    │Confidence check  │        │
                    │    │≥ 60%? Keep tier  │        │
                    │    │< 60%? Upgrade    │        │
                    │    └──────────────────┘        │
                    └──────────┬────────────────────┘
                               │
                               ▼
                    ┌───────────────────────────────┐
                    │   DISPATCH                     │
                    │   Tries chosen provider        │
                    │   ┌─────┐                      │
                    │   │Fail?│───Yes──→ Fall back   │
                    │   └─────┘          to next tier│
                    │      No                       │
                    │      ▼                        │
                    │   Response sent back           │
                    │   (with routing metadata)      │
                    └───────────────────────────────┘
```

---

## Quick Reference: All 23 Features

| # | Feature | Category | Type | Description |
|---|---|---|---|---|
| 1 | char_count | Lexical | float | Total characters |
| 2 | word_count | Lexical | float | Word count (via textstat) |
| 3 | sentence_count | Lexical | float | Sentence count |
| 4 | avg_word_length | Lexical | float | Mean characters per word |
| 5 | unique_word_ratio | Lexical | float | Unique / total words |
| 6 | avg_sentence_len | Readability | float | Mean words per sentence |
| 7 | fk_grade | Readability | float | Flesch-Kincaid grade level |
| 8 | has_code_block | Structure | binary (0/1) | Contains triple backticks |
| 9 | has_numbers | Structure | binary (0/1) | Contains digits |
| 10 | question_count | Structure | float | Number of `?` characters |
| 11 | comma_count | Structure | float | Number of `,` characters |
| 12 | has_bullet | Structure | binary (0/1) | Uses bullet point syntax |
| 13 | has_constraints | Structure | binary (0/1) | Uses "must", "require", etc. |
| 14 | caps_ratio | Structure | float (0-1) | Uppercase / total chars |
| 15 | is_coding | Pattern flag | binary (0/1) | Code-related keywords |
| 16 | is_debugging | Pattern flag | binary (0/1) | Debugging keywords |
| 17 | is_reasoning | Pattern flag | binary (0/1) | Reasoning keywords |
| 18 | is_creative | Pattern flag | binary (0/1) | Creative writing keywords |
| 19 | is_multistep | Pattern flag | binary (0/1) | Multi-step task keywords |
| 20 | is_math | Pattern flag | binary (0/1) | Math keywords |
| 21 | is_summarize | Pattern flag | binary (0/1) | Summarization keywords |
| 22 | is_simple_qa | Pattern flag | binary (0/1) | Simple question keywords |
| 23 | complexity_score | Composite | float | Heuristic difficulty estimate |

---

*Last updated: June 2026*
