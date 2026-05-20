# How ClassiRoute Works — A Complete Guide

This document explains the entire journey of your request — from the moment you type a message to when you see a response — and how ClassiRoute decides which AI model to use.

---

## The Big Picture

ClassiRoute is a **smart router** for AI models. Instead of manually choosing between a cheap model, a medium model, or an expensive model for every request, ClassiRoute does it automatically.

Think of it like this: you don't use a sledgehammer to crack a nut, and you don't use a nutcracker to build a house. ClassiRoute figures out which tool is right for each job.

---

## The Three Tiers

Every Virtual Key you create has **three tiers** of models configured:

| Tier | Name | When it's picked |
|---|---|---|
| **Tier 0** | Weak | Very simple requests — basic Q&A, definitions, simple summaries |
| **Tier 1** | Mid | Moderate complexity — explanations, comparisons, creative writing, planning |
| **Tier 2** | Strong | Hard problems — complex coding, debugging, math, system design |

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

When you type a message, ClassiRoute's **Feature Extractor** reads it like a detective looking for clues. It measures **23 different things** about your prompt:

#### 📏 Length & Readability
- How many characters, words, and sentences?
- How long are the words and sentences on average?
- What's the reading grade level (Flesch-Kincaid)?

#### 🔍 Pattern Detection (The Keyword Scanner)
The system looks for specific keywords that hint at what kind of task this is:

| Pattern | Example keywords | What it suggests |
|---|---|---|
| `is_coding` | code, implement, function, class, algorithm, API | "This is a programming task" |
| `is_debugging` | debug, error, fix, bug, crash, not working | "This needs troubleshooting" |
| `is_reasoning` | explain, why, how does, analyze, compare | "This needs careful thinking" |
| `is_multistep` | design, plan, build, architecture, system | "This has multiple steps" |
| `is_math` | solve, calculate, equation, probability, proof | "This involves math" |
| `is_simple_qa` | what is, who is, define, meaning of | "This is a simple question" |
| `is_creative` | poem, story, creative, imagine, compose | "This is creative writing" |
| `is_summarize` | summarize, tl;dr, brief, overview | "This needs condensing" |

#### 🚩 Other Flags
- **has_code_block** — Does your prompt contain triple backticks (\`\`\`)?
- **has_numbers** — Are there digits in your prompt?
- **has_bullets** — Are you using bullet points?
- **has_constraints** — Do you use words like "must", "require", "exactly"?

#### 📊 Complexity Score

Based on these clues, the system calculates a **complexity score** — a rough estimate of how hard the task is:

```
is_coding?      → +2.0
is_debugging?   → +2.0
is_multistep?   → +2.5    ← "Plan", "Build", "Design" add the most weight
is_reasoning?   → +2.0
is_math?        → +1.5
has_code_block? → +1.5
has_constraints?→ +1.0
Hard to read?   → +1.0    (FK grade > 12)
```

**Example:** For the prompt *"Design a sales plan for an AI automation agency"*:
- The word **"Design"** triggers `is_multistep` → +2.5
- Total score: **2.5**
- This falls in the **mid** range (between 2.0 and 4.0)

---

### Step 2: Routing Decision (Which Tier?)

Once the features are extracted, ClassiRoute decides which tier to use. It has **two ways** to make this decision:

#### Path A: The ML Classifier (Preferred)

If a pre-trained AI model file (`router_classifier.pkl`) is loaded, ClassiRoute uses it. This is a machine learning model that was trained on thousands of example prompts.

**How it works:**
1. Your prompt's 23 measurements are fed into the classifier
2. It outputs probabilities for each tier:
   ```
   Weak:   12%
   Mid:    78%  ← highest
   Strong: 10%
   ```
3. It picks the tier with the highest probability
4. **Confidence check:** If the probability is below 60%, the system gets cautious and upgrades the tier by one (see "The Upgrade Safety Net" below)

#### Path B: The Heuristic (Fallback)

If no ML model file is available, ClassiRoute uses a simple rule-based approach:

```
Complexity score < 2.0  → Weak  (tier 0)
Complexity score < 4.0  → Mid   (tier 1)
Complexity score ≥ 4.0  → Strong (tier 2)
```

#### 🔒 The Upgrade Safety Net

If the ML classifier is **not very sure** about its decision (confidence < 60%) AND the chosen tier is not already Strong, the system **upgrades** by one level:

```
Example: Classifier predicts Mid at 55% confidence
         → 55% < 60%, so upgrade to Strong

Example: Classifier predicts Weak at 45% confidence
         → 45% < 60%, so upgrade to Mid

Example: Classifier predicts Strong at 80% confidence
         → 80% ≥ 60%, stays Strong
```

This is a safety feature — better to use a slightly stronger model than risk a bad answer from a weak one.

---

### Step 3: Dispatch (Sending the Request)

After a tier is chosen, ClassiRoute looks at your Virtual Key to find:
- Which **model name** is configured for that tier (e.g., `gpt-4o`, `claude-3-sonnet`)
- The **API key** and **base URL** for that provider

It sends your request to that provider.

#### 🔁 Auto-Fallback (If Something Goes Wrong)

If the chosen provider fails (wrong API key, network error, rate limit, model unavailable), ClassiRoute automatically **falls back** to the next lower tier:

```
Strong fails → tries Mid → Mid fails → tries Weak → gives error
```

This means your request always has the best chance of getting a response, even if your Strong provider is having issues.

**Important:** If a fallback happens, the response will show which tier actually handled it. For example, if Strong was chosen but failed and Mid responded, you'll see "Mid" as the responding tier.

---

## Real Examples

### Example 1: "What is the capital of France?"

| Step | Result |
|---|---|
| Feature scan | `is_simple_qa` = 1 (matches "what is") |
| Complexity score | 0.0 (no flags fired) |
| Heuristic routing | Score 0.0 < 2.0 → **Weak** |
| ML routing | Weak at 90% confidence → **Weak** |
| What happens | Goes to your Weak model (fast + cheap) ✅ |

### Example 2: "Explain how quantum computers work and compare them to classical computers"

| Step | Result |
|---|---|
| Feature scan | `is_reasoning` = 1 (matches "explain", "how", "compare") |
| Complexity score | 2.0 (reasoning only) |
| Heuristic routing | Score 2.0 ≥ 2.0 and < 4.0 → **Mid** |
| ML routing | Mid at 75% confidence → **Mid** |
| What happens | Goes to your Mid model ✅ |

### Example 3: "Design a distributed database system that handles 10K writes/sec with strong consistency. Must support multi-region replication and automatic failover. Implement the consensus algorithm."

| Step | Result |
|---|---|
| Feature scan | `is_multistep` = 1 ("Design"), `is_coding` = 1 ("implement", "algorithm"), `has_constraints` = 1 ("Must") |
| Complexity score | 2.5 + 2.0 + 1.0 = 5.5 |
| Heuristic routing | Score 5.5 ≥ 4.0 → **Strong** |
| ML routing | Mid at 50% confidence → confidence < 60% → **upgrade to Strong** |
| What happens | Goes to your Strong model ✅ |

---

## Creating a Virtual Key (With Validation)

When you create a Virtual Key in the UI:

1. You fill in the model name, API key, and base URL for all three tiers
2. When you click **Create Key**, ClassiRoute doesn't just save the form — it first **checks all three providers** by hitting their `/models` endpoint
3. For each tier, it verifies:
   - ✅ The base URL is reachable
   - ✅ The API key is valid (no 401 error)
   - ✅ The model name actually exists on that provider
4. **If any tier fails validation**, the key is **not created** and you'll see an error explaining which tier failed and why
5. **Only if all three pass** does the key get created and stored

This saves you from creating a key that won't work later.

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
                    │   • Scans for keywords         │
                    │   • Calculates complexity      │
                    └──────────┬────────────────────┘
                               │
                    ┌──────────▼────────────────────┐
                    │   ROUTER                       │
                    │ ┌─────────┐  ┌──────────────┐ │
                    │ │ML       │  │Heuristic     │ │
                    │ │Classifier│  │(fallback)    │ │
                    │ └────┬────┘  └──────┬───────┘ │
                    │      └──────┬───────┘          │
                    │             ▼                  │
                    │    Tier decided                │
                    │    (Weak / Mid / Strong)        │
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
                    └───────────────────────────────┘
```
