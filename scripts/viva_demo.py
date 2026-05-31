#!/usr/bin/env python3
"""
ClassiRoute Viva Demo — Intelligent LLM Routing Showcase
=========================================================

A terminal-based demo that puts ClassiRoute's multi-tier routing through its paces.
A LangChain ReAct agent with several tools processes queries of varying complexity.
ClassiRoute automatically routes each query to the optimal model — cheap for simple
facts, beefy for multi-hop reasoning.

Dependencies:
    pip install langchain langchain-openai

Usage:
    python3 scripts/viva_demo.py
"""

import json
import re
import sys
import textwrap
import time
import urllib.request
import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional

# ── 1. Configuration (no JWT, no login — just a key + URL) ────────────────────

DEMO_API_KEY = "clr-a34250df6100cd054404581b720b2f2edeef824d176681b81fed50495cddc17d"
DEMO_BASE_URL = "http://127.0.0.1:8000/"

# ── 2. ANSI styling for terminal output ───────────────────────────────────────

class T:
    """Terminal style helpers."""
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    GRAY = "\033[90m"
    RESET = "\033[0m"

    @staticmethod
    def bold(s): return f"{T.BOLD}{s}{T.RESET}"

    @staticmethod
    def green(s): return f"{T.GREEN}{s}{T.RESET}"

    @staticmethod
    def yellow(s): return f"{T.YELLOW}{s}{T.RESET}"

    @staticmethod
    def blue(s): return f"{T.BLUE}{s}{T.RESET}"

    @staticmethod
    def magenta(s): return f"{T.MAGENTA}{s}{T.RESET}"

    @staticmethod
    def cyan(s): return f"{T.CYAN}{s}{T.RESET}"

    @staticmethod
    def red(s): return f"{T.RED}{s}{T.RESET}"

    @staticmethod
    def gray(s): return f"{T.GRAY}{s}{T.RESET}"

    @staticmethod
    def dim(s): return f"{T.DIM}{s}{T.RESET}"


SEP = "━" * 72
HALF = "─" * 72

# ── 3. Tools for the agent ────────────────────────────────────────────────────

CAPITALS: dict[str, str] = {
    "india": "New Delhi", "france": "Paris", "japan": "Tokyo",
    "germany": "Berlin", "brazil": "Brasília", "usa": "Washington, D.C.",
    "canada": "Ottawa", "australia": "Canberra", "italy": "Rome",
    "china": "Beijing", "spain": "Madrid", "uk": "London",
    "russia": "Moscow", "south korea": "Seoul", "singapore": "Singapore",
}

CURRENCIES: dict[str, tuple[str, float]] = {
    "usd": ("US Dollar", 1.0), "eur": ("Euro", 0.92), "gbp": ("British Pound", 0.79),
    "jpy": ("Japanese Yen", 149.5), "inr": ("Indian Rupee", 83.1),
    "cad": ("Canadian Dollar", 1.36), "aud": ("Australian Dollar", 1.53),
    "brl": ("Brazilian Real", 4.97), "cny": ("Chinese Yuan", 7.24),
    "krw": ("South Korean Won", 1325.0),
}

RECIPES: dict[str, str] = {
    "pasta": "Boil pasta 10 min. Sauté garlic in olive oil, add tomatoes, simmer 15 min. Mix.",
    "pancake": "1 cup flour, 1 egg, 1 cup milk, 2 tbsp sugar. Fry on medium heat 2 min each side.",
    "omelette": "2 eggs beaten, salt, pepper. Cook in butter 3 min, fold, serve.",
    "salad": "Chop lettuce, tomatoes, cucumber. Dress with olive oil, lemon, salt.",
}


@dataclass
class ToolCall:
    tool: str
    args: str
    result: str


@dataclass
class ScenarioResult:
    name: str
    query: str
    answer: str
    model_used: str
    tier_name: str
    tier_confidence: float
    token_usage: dict
    latency_s: float
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: Optional[str] = None


# ── 4. Agent helpers ──────────────────────────────────────────────────────────

from langchain.tools import tool
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression. Input: a math expression like '1847 * 23 + 456'."""
    sanitized = re.sub(r"[^0-9+\-*/().,\s]", "", expression)
    if not sanitized.strip():
        return "Error: empty expression after sanitization"
    try:
        # Replace commas for thousand-separator compatibility
        sanitized = sanitized.replace(",", "")
        return str(eval(sanitized, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


@tool
def word_counter(text: str) -> str:
    """Count words in a given text. Input: any text string."""
    return str(len(text.strip().split()))


@tool
def capital_lookup(country: str) -> str:
    """Look up the capital city of any country."""
    key = country.strip().lower()
    if key in CAPITALS:
        return f"The capital of {country.strip()} is {CAPITALS[key]}."
    # Fuzzy match: try partial match
    matches = [k for k in CAPITALS if k in key or key in k]
    if matches:
        return f"The capital of {matches[0].title()} is {CAPITALS[matches[0]]}."
    return f"Capital not found for: {country}"


@tool
def currency_converter(amount_and_from_and_to: str) -> str:
    """Convert currency. Input format: '<amount> <from_currency> to <to_currency>'.
    Supported currencies: USD, EUR, GBP, JPY, INR, CAD, AUD, BRL, CNY, KRW."""
    # Parse input
    m = re.match(
        r"(\d+\.?\d*)\s*([a-zA-Z]{3})\s*(?:to|in|->)\s*([a-zA-Z]{3})",
        amount_and_from_and_to,
    )
    if not m:
        return ("Error: use format like '100 USD to EUR'. "
                f"Supported: {', '.join(sorted(CURRENCIES))}")

    amount = float(m.group(1))
    from_c = m.group(2).lower()
    to_c = m.group(3).lower()

    if from_c not in CURRENCIES:
        return f"Unknown currency: {from_c}"
    if to_c not in CURRENCIES:
        return f"Unknown currency: {to_c}"

    usd_value = amount / CURRENCIES[from_c][1]
    result = usd_value * CURRENCIES[to_c][1]
    return f"{amount} {CURRENCIES[from_c][0]} ({from_c.upper()}) = {result:.2f} {CURRENCIES[to_c][0]} ({to_c.upper()})"


@tool
def recipe_lookup(dish: str) -> str:
    """Get a simple recipe for a dish. Choices: pasta, pancake, omelette, salad."""
    key = dish.strip().lower()
    if key in RECIPES:
        return f"Recipe for {dish.strip()}: {RECIPES[key]}"
    return f"No recipe found for: {dish}"


# ── 5. Routing info fetcher (separate lightweight call) ───────────────────────

def fetch_routing(query: str) -> dict:
    """Make a minimal API call just to extract ClassiRoute routing metadata."""
    payload = json.dumps({
        "model": "classiroute",
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 5,
    }).encode()
    req = urllib.request.Request(
        f"{DEMO_BASE_URL}v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEMO_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            meta = body.get("x-llmrouter", {})
            meta["model"] = body.get("model", "classiroute")
            return meta
    except Exception as e:
        return {"tier_name": "unknown", "model": "classiroute", "error": str(e)}


# ── 6. Pricing model (illustrative per-1K-token costs) ────────────────────────

TIER_PRICING = {
    "weak":   {"input_1k": 0.040, "output_1k": 0.080, "label": "Llama 3.2 1B"},
    "mid":    {"input_1k": 0.120, "output_1k": 0.240, "label": "Llama 3.2 3B"},
    "strong": {"input_1k": 0.300, "output_1k": 0.600, "label": "Llama 3.3 8B"},
}

ESTIMATED_STRONG_COST = 0.002  # Estimated cost per call if always using strong model


def estimate_cost(token_usage: dict, tier_name: str) -> float:
    """Estimate cost in USD for a single request based on token usage and tier."""
    pricing = TIER_PRICING.get(tier_name)
    if not pricing:
        return 0.0
    input_tokens = token_usage.get("prompt_tokens", 0)
    output_tokens = token_usage.get("completion_tokens", 0)
    cost = (input_tokens / 1000 * pricing["input_1k"]
            + output_tokens / 1000 * pricing["output_1k"])
    return cost


# ── 7. Demo scenarios ─────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "name": "Quick Fact",
        "query": "What is the capital of Japan?",
        "desc": "Trivial lookup → cheap tier",
    },
    {
        "name": "Arithmetic",
        "query": "Calculate 1847 multiplied by 23 plus 456",
        "desc": "Basic computation → cheap tier",
    },
    {
        "name": "Rate Limiter Code",
        "query": "Implement a distributed rate limiter in Python using Redis sorted sets with a sliding window algorithm. Include error handling.",
        "desc": "Coding task — mid-tier model",
    },
    {
        "name": "Multi-hop Analysis",
        "query": "Look up the capitals of France, India, and Brazil. For each capital, count the number of letters. Calculate: (sum of letter counts) times 8000000 divided by 1000. Then look up the recipe for pasta.",
        "desc": "Multi-tool reasoning — mid-tier model",
    },
    {
        "name": "System Design",
        "query": "Design a microservice architecture for an e-commerce platform. Cover 10+ services, async messaging, CQRS, event sourcing, circuit breakers, and distributed tracing. Give a detailed implementation plan.",
        "desc": "Complex architecture → strongest tier",
    },
]


# ── 8. Output helpers ─────────────────────────────────────────────────────────

def print_banner():
    """Print the demo header."""
    print()
    print(T.cyan(f"  {SEP}"))
    print(T.cyan(f"  ╔══════════════════════════════════════════════════════════════════════╗"))
    print(T.cyan(f"  ║                    {T.bold('ClassiRoute · Viva Demo')}                   ║"))
    print(T.cyan(f"  ║              {T.dim('Intelligent Multi-Tier LLM Routing')}               ║"))
    print(T.cyan(f"  ╚══════════════════════════════════════════════════════════════════════╝"))
    print(T.cyan(f"  {SEP}"))
    print()
    print(T.dim("  A single LangChain ReAct agent — one API, one key."))
    print(T.dim("  Every query is automatically routed to the optimal model tier."))
    print(T.dim("  Weak models handle simple facts. Strong models tackle multi-hop reasoning."))
    print()


def print_scenario_header(scenario: dict, idx: int, total: int):
    """Print scenario header block."""
    print()
    print(T.blue(f"  {HALF}"))
    print(T.bold(f"  SCENARIO {idx}/{total}  │  {scenario['name']}"))
    print(T.blue(f"  {HALF}"))
    print(f"  {T.dim(scenario['desc'])}")
    print(f"  {T.gray('Query:')} {scenario['query']}")
    print()


def print_tool_calls(tool_calls: list[ToolCall]):
    """Print tool call trace, if any."""
    if not tool_calls:
        return
    print(f"  {T.dim('Tool calls:')}")
    for i, tc in enumerate(tool_calls, 1):
        print(f"    {T.dim(f'{i}.')} {T.yellow(tc.tool)}({T.gray(tc.args)})")
        print(f"       → {tc.result[:90]}{'…' if len(tc.result) > 90 else ''}")
    print()


def print_metrics(result: ScenarioResult):
    """Print the metrics block for a single scenario."""
    print(f"  {T.green('✓ Done')}  {result.latency_s:.2f}s")
    print()
    print(f"  {T.bold('Routing:')}")
    tier_color = {
        "weak": T.green, "mid": T.yellow, "strong": T.red
    }.get(result.tier_name, T.cyan)
    print(f"    Tier       :  {tier_color(result.tier_name.upper())}  "
          f"(confidence: {result.tier_confidence:.1%})")
    print(f"    Model      :  {T.cyan(result.model_used)}")
    print(f"    Latency    :  {result.latency_s:.2f}s")
    cost = result.token_usage.get("cost", 0)
    cost_str = f"${cost:.6f}" if cost > 0 else "N/A"
    print(f"    Est. Cost  :  {cost_str}")
    if cost > 0:
        always_strong = result.token_usage.get("always_strong_cost", 0)
        if always_strong > 0:
            saved = (1 - cost / always_strong) * 100
            print(f"    Savings   :  {T.green(f'{saved:.1f}%')} vs always-using-strong-model")
    print()


def print_footer():
    """Print demo footer."""
    print()
    print(f"  {T.bold('─' * 72)}")
    print()

# ── 9. Summary dashboard ──────────────────────────────────────────────────────

def print_summary(results: list[ScenarioResult]):
    """Print a summary table with cost comparison."""
    print()
    print(T.magenta(f"  {SEP}"))
    print(T.magenta(f"  ╔══════════════════════════════════════════════════════════════════════╗"))
    print(T.magenta(f"  ║                      {T.bold('DASHBOARD SUMMARY')}                        ║"))
    print(T.magenta(f"  ╚══════════════════════════════════════════════════════════════════════╝"))
    print(T.magenta(f"  {SEP}"))
    print()

    # ── Table header ──
    hdr = (f"  {T.bold('SCENARIO'):<28} {T.bold('TIER'):<10} {T.bold('MODEL'):<22} "
           f"{T.bold('COST'):<14} {T.bold('TIME')}")
    print(hdr)
    print(f"  {T.gray('─' * 84)}")

    total_cost = 0.0
    total_strong_cost = 0.0
    total_time = 0.0
    tier_counts = {}

    for r in results:
        tier_counts[r.tier_name] = tier_counts.get(r.tier_name, 0) + 1
        cost = r.token_usage.get("cost", 0)
        strong = r.token_usage.get("always_strong_cost", 0)
        total_cost += cost
        total_strong_cost += strong
        total_time += r.latency_s

        tier_color = {"weak": T.green, "mid": T.yellow, "strong": T.red}.get(
            r.tier_name, T.cyan
        )
        label = TIER_PRICING.get(r.tier_name, {}).get("label", "?")
        cost_str = f"${cost:.6f}" if cost > 0 else "N/A"
        print(
            f"  {r.name:<28} {tier_color(r.tier_name.upper()):<10} "
            f"{label:<22} {cost_str:<14} {r.latency_s:.2f}s"
        )

    print(f"  {T.gray('─' * 84)}")

    # ── Footer row ──
    total_str = f"${total_cost:.6f}" if total_cost > 0 else "N/A"
    print(
        f"  {T.bold('TOTAL'):<28} {'' :<10} "
        f"{T.bold(total_str):<22} {'':<14} {T.bold(f'{total_time:.2f}s')}"
    )

    print()
    print(f"  {T.bold('Tier Distribution:')}")
    for tier in ["weak", "mid", "strong"]:
        count = tier_counts.get(tier, 0)
        bar = "█" * count + "░" * (max(5, sum(tier_counts.values())) - count)
        label = TIER_PRICING.get(tier, {}).get("label", tier)
        color = {"weak": T.green, "mid": T.yellow, "strong": T.red}.get(tier, T.cyan)
        plural = "query" if count == 1 else "queries"
        print(f"    {color(tier.upper()):<10} {label:<22} {bar} {count} {plural}")

    # ── Cost savings ──
    if total_strong_cost > 0:
        saved_pct = (1 - total_cost / total_strong_cost) * 100
        saved_dollars = total_strong_cost - total_cost
        print()
        print(f"  {T.bold('Cost Analysis:')}")
        print(f"    Actual cost          :  {T.green(f'${total_cost:.6f}')}")
        print(f"    If always-strong     :  {T.red(f'${total_strong_cost:.6f}')}")
        print(f"    {T.green('You saved')}            :  {T.bold(T.green(f'{saved_pct:.1f}%  (${saved_dollars:.6f})'))}")
        print()

    print(T.magenta(f"  {SEP}"))
    print()


# ── 10. Main ──────────────────────────────────────────────────────────────────

def extract_tool_calls(messages: list) -> list[ToolCall]:
    """Walk the message list to trace tool calls and results."""
    calls = []
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = getattr(tc, "name", None) or tc.get("name", "?")
                args = getattr(tc, "args", None) or tc.get("args", {})
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)

                # Find the corresponding tool result message
                tool_call_id = getattr(tc, "id", None) or tc.get("id", "")
                result = ""
                for j in range(i + 1, len(messages)):
                    nm = messages[j]
                    if isinstance(nm, ToolMessage) and getattr(nm, "tool_call_id", None) == tool_call_id:
                        result = getattr(nm, "content", "") or ""
                        break

                calls.append(ToolCall(tool=tool_name, args=args_str, result=result))
    return calls


def extract_answer(messages: list) -> str:
    """Extract the final AI answer (last AIMessage without tool_calls)."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            tc = getattr(msg, "tool_calls", None) or []
            if not tc:
                content = getattr(msg, "content", "") or ""
                if content.strip():
                    return content.strip()
    return "(no answer found)"


def main():
    print_banner()

    # ── Init agent ──
    llm = ChatOpenAI(
        openai_api_key=DEMO_API_KEY,
        openai_api_base=f"{DEMO_BASE_URL}v1",
        model_name="classiroute",
        temperature=0,
    )
    agent = create_agent(
        model=llm,
        tools=[calculator, word_counter, capital_lookup, currency_converter, recipe_lookup],
    )

    results: list[ScenarioResult] = []

    for idx, scenario in enumerate(SCENARIOS, 1):
        query = scenario["query"]

        print_scenario_header(scenario, idx, len(SCENARIOS))

        # ── Fire routing probe + agent in parallel ──
        tier_name = "unknown"
        confidence = 0.0
        model_used = "classiroute"
        start = time.time()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                routing_future = pool.submit(fetch_routing, query)
                agent_future = pool.submit(agent.invoke, {"messages": [{"role": "user", "content": query}]})
                result = agent_future.result(timeout=180)
                elapsed = time.time() - start

                # Collect routing info (already done in parallel)
                routing = routing_future.result(timeout=30)
                tier_name = routing.get("tier_name", "unknown")
                confidence = float(routing.get("confidence", 0))
                model_used = routing.get("model", "classiroute")

            # ── Extract results ──
            messages = result.get("messages", [])
            answer = extract_answer(messages)
            tool_calls = extract_tool_calls(messages)

            last_msg = messages[-1] if messages else None
            usage = {}
            if last_msg and hasattr(last_msg, "response_metadata"):
                usage = last_msg.response_metadata.get("token_usage", {})

            cost = estimate_cost(usage, tier_name)
            strong_cost = estimate_cost(usage, "strong")
            usage["cost"] = cost
            usage["always_strong_cost"] = strong_cost

            scenario_result = ScenarioResult(
                name=scenario["name"], query=query, answer=answer,
                model_used=model_used, tier_name=tier_name,
                tier_confidence=confidence, token_usage=usage,
                latency_s=elapsed, tool_calls=tool_calls,
            )

            # ── Print output ──
            print(f"  {T.bold(T.cyan('Answer:'))} {answer}")
            print()
            if tool_calls:
                print_tool_calls(tool_calls)
            print_metrics(scenario_result)

        except Exception as agent_err:
            elapsed = time.time() - start
            scenario_result = ScenarioResult(
                name=scenario["name"], query=query, answer="",
                model_used=model_used, tier_name=tier_name,
                tier_confidence=confidence, token_usage={},
                latency_s=elapsed, error=str(agent_err),
            )
            print(f"  {T.red(f'✗ Error: {agent_err}')}")
            print()

        results.append(scenario_result)

    # ── Summary ──
    print_summary(results)

    print(T.dim("  " + HALF))
    print(T.dim("  ClassiRoute automatically routed each query to its optimal model tier."))
    print(T.dim("  One API, one key, one agent — intelligent routing under the hood."))
    print()
    print(T.cyan("  Demo complete. ✓"))
    print()


if __name__ == "__main__":
    main()
