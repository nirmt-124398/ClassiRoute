"""
Standalone LangChain ReAct agent demo — ClassiRoute as LLM backend.

Dependencies:
    pip install langchain langchain-openai

Usage:
    python3 scripts/demo_agent.py
"""

import re

# ── config (hardcoded — no login, no JWT) ─────────────────────────────────────
DEMO_API_KEY = (
    "clr-a34250df6100cd054404581b720b2f2edeef824d176681b81fed50495cddc17d"
)
DEMO_BASE_URL = "http://127.0.0.1:8000/"

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool

# ── tools ─────────────────────────────────────────────────────────────────────


@tool
def calculator(expression: str) -> str:
    """Evaluates a mathematical expression string."""
    if not re.match(r"^[\d\s+\-*/().,]+$", expression):
        return "Error: invalid characters in expression"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error evaluating expression: {e}"


@tool
def word_counter(text: str) -> str:
    """Counts the number of words in a given text."""
    return str(len(text.strip().split()))


CAPITALS: dict[str, str] = {
    "india": "New Delhi",
    "france": "Paris",
    "japan": "Tokyo",
    "germany": "Berlin",
    "brazil": "Brasília",
    "usa": "Washington, D.C.",
    "canada": "Ottawa",
    "australia": "Canberra",
    "italy": "Rome",
    "china": "Beijing",
}


@tool
def capital_lookup(country: str) -> str:
    """Returns the capital city of a given country."""
    return CAPITALS.get(
        country.strip().lower(), f"Capital not found for: {country}"
    )


# ── LLM + agent setup ─────────────────────────────────────────────────────────

llm = ChatOpenAI(
    openai_api_key=DEMO_API_KEY,
    openai_api_base=DEMO_BASE_URL + "v1",
    model_name="classiroute",
)

agent = create_agent(
    model=llm,
    tools=[calculator, word_counter, capital_lookup],
)

# ── tasks ─────────────────────────────────────────────────────────────────────

TASKS: list[str] = [
    "What is 1847 multiplied by 23 plus 456?",
    "How many words are in this sentence: The quick brown fox jumps over the lazy dog",
    "What is the capital of Japan?",
    "What is the capital of Germany and how many words are in its name?",
]

SEPARATOR = "━" * 50

for task in TASKS:
    result = agent.invoke({"messages": [{"role": "user", "content": task}]})

    # -- extract intermediate thinking and final answer --
    messages = result.get("messages", [])
    thinking_lines: list[str] = []
    final_answer = ""

    for msg in messages:
        role = getattr(msg, "type", "") or ""
        content = getattr(msg, "content", "") or ""

        if role == "ai" and content:
            # If it has tool_calls, it's a reasoning step; otherwise final answer
            tool_calls = getattr(msg, "tool_calls", []) or []
            if tool_calls:
                # Strip content to first ~80 chars as a thought preview
                preview = content.strip()[:120]
                if preview:
                    thinking_lines.append(preview)
            else:
                final_answer = content.strip()

    # -- print output block --
    print(f"\n{SEPARATOR}")
    print(f"Task      : {task}")
    for t in thinking_lines:
        print(f"Thinking  : {t}")
    print(f"Answer    : {final_answer}")
    print(f"Routed to : see backend logs")
    print(SEPARATOR)

print(
    "\nClassiRoute automatically routed all LangChain "
    "LLM calls based on prompt complexity.\n"
    "No model configuration needed in the agent code."
)
