# Unified LLM Gateway — Complete Build Plan

> **Stack:** Python (FastAPI) backend · Next.js frontend  
> **Starting point:** Nvidia NIM already integrated  
> **Goal:** Multi-provider gateway where users bring their own API key

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Folder Structure](#2-folder-structure)
3. [Core Architecture](#3-core-architecture)
4. [Phase 1 — Refactor NIM into Adapter Pattern](#4-phase-1--refactor-nim-into-adapter-pattern)
5. [Phase 2 — Add OpenAI Provider](#5-phase-2--add-openai-provider)
6. [Phase 3 — Add Anthropic Provider](#6-phase-3--add-anthropic-provider)
7. [Phase 4 — Add Gemini Provider](#7-phase-4--add-gemini-provider)
8. [Streaming](#8-streaming)
9. [Error Handling](#9-error-handling)
10. [Frontend Integration](#10-frontend-integration)
11. [API Contract](#11-api-contract)
12. [Verifiable Milestones](#12-verifiable-milestones)
13. [What NOT to Build Yet](#13-what-not-to-build-yet)

---

## 1. Project Overview

A self-hosted API gateway that sits between the user's frontend and multiple LLM providers. The user selects a provider, enters their own API key, and the backend handles request transformation, routing, and response normalization.

```
User (Frontend)
    │
    │  { provider, api_key, model, messages }
    ▼
FastAPI Backend (Gateway)
    │
    ├──► Nvidia NIM
    ├──► OpenAI
    ├──► Anthropic
    └──► Gemini
```

Every provider returns the same normalized response shape — the frontend never needs to know which provider was used.

---

## 2. Folder Structure

```
backend/
├── main.py                  # FastAPI app, single /chat endpoint
├── router.py                # Maps provider name → Provider class
├── base.py                  # Abstract base class all providers inherit
├── providers/
│   ├── nvidia.py            # Existing NIM logic, refactored
│   ├── openai.py
│   ├── anthropic.py
│   └── gemini.py
└── schemas.py               # Pydantic request/response models

frontend/
├── app/
│   └── page.tsx             # Main chat UI
├── components/
│   ├── ProviderSelector.tsx # Dropdown for provider selection
│   ├── ApiKeyInput.tsx      # Masked input for user's API key
│   └── ChatWindow.tsx       # Message display + streaming output
└── lib/
    └── api.ts               # Fetch wrapper for /chat endpoint
```

---

## 3. Core Architecture

### 3.1 The Unified Request Schema

Every request from the frontend to the backend uses this exact shape. Never change this contract — only the backend internals change per provider.

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "model": "claude-3-5-sonnet-20241022",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Hello!" }
  ],
  "stream": false
}
```

### 3.2 The Unified Response Schema

Every provider's response is normalized to this shape before being returned to the frontend.

```json
{
  "content": "Hello! How can I help you?",
  "model": "claude-3-5-sonnet-20241022",
  "provider": "anthropic",
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 8,
    "total_tokens": 20
  }
}
```

### 3.3 The Base Provider (base.py)

This is the contract every provider must fulfill. Never call providers directly — always go through this interface.

```python
# base.py
from abc import ABC, abstractmethod

class BaseProvider(ABC):

    @abstractmethod
    def transform_request(self, messages: list, model: str, **kwargs) -> dict:
        """Convert unified messages format → provider-specific payload"""
        pass

    @abstractmethod
    def transform_response(self, raw: dict) -> dict:
        """Convert provider-specific response → unified response schema"""
        pass

    @abstractmethod
    def chat(self, messages: list, model: str, api_key: str, **kwargs) -> dict:
        """Make the actual HTTP call, return normalized response"""
        pass
```

---

## 4. Phase 1 — Refactor NIM into Adapter Pattern

**Goal:** Wrap existing NIM code inside `NimProvider` without changing any behavior. This proves the pattern works before adding new providers.

### providers/nvidia.py

```python
import httpx
from base import BaseProvider

class NimProvider(BaseProvider):
    BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

    def transform_request(self, messages, model, **kwargs):
        # NIM uses OpenAI format — no transformation needed
        return {
            "model": model,
            "messages": messages,
            **kwargs
        }

    def transform_response(self, raw) -> dict:
        return {
            "content": raw["choices"][0]["message"]["content"],
            "model": raw["model"],
            "provider": "nvidia",
            "usage": raw.get("usage", {})
        }

    def chat(self, messages, model, api_key, **kwargs):
        payload = self.transform_request(messages, model, **kwargs)
        r = httpx.post(
            self.BASE_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60
        )
        r.raise_for_status()
        return self.transform_response(r.json())
```

### Verify Phase 1

Send this curl — should return same result as before the refactor:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "nvidia",
    "api_key": "your-nim-key",
    "model": "meta/llama-3.1-8b-instruct",
    "messages": [{"role": "user", "content": "Say hello"}]
  }'
```

---

## 5. Phase 2 — Add OpenAI Provider

OpenAI and NIM share the same API format. This phase is mostly copy-paste with a different base URL.

### providers/openai.py

```python
import httpx
from base import BaseProvider

class OpenAIProvider(BaseProvider):
    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def transform_request(self, messages, model, **kwargs):
        return {
            "model": model,
            "messages": messages,
            **kwargs
        }

    def transform_response(self, raw) -> dict:
        return {
            "content": raw["choices"][0]["message"]["content"],
            "model": raw["model"],
            "provider": "openai",
            "usage": raw.get("usage", {})
        }

    def chat(self, messages, model, api_key, **kwargs):
        payload = self.transform_request(messages, model, **kwargs)
        r = httpx.post(
            self.BASE_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60
        )
        r.raise_for_status()
        return self.transform_response(r.json())
```

### Common OpenAI models to support

| Model String | Notes |
|---|---|
| `gpt-4o` | Default recommendation |
| `gpt-4o-mini` | Cheap, fast |
| `gpt-4-turbo` | Long context |
| `o1-mini` | Reasoning model |

---

## 6. Phase 3 — Add Anthropic Provider

Anthropic is the most different. Three key differences from OpenAI format:

1. `system` prompt is a **top-level field**, not inside `messages`
2. Headers use `x-api-key` not `Authorization: Bearer`
3. Response is in `content[0].text` not `choices[0].message.content`

### providers/anthropic.py

```python
import httpx
from base import BaseProvider

class AnthropicProvider(BaseProvider):
    BASE_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def transform_request(self, messages, model, **kwargs):
        # Extract system message — Anthropic requires it separately
        system = next(
            (m["content"] for m in messages if m["role"] == "system"),
            None
        )
        user_msgs = [m for m in messages if m["role"] != "system"]

        payload = {
            "model": model,
            "messages": user_msgs,
            "max_tokens": kwargs.pop("max_tokens", 1024),
        }
        if system:
            payload["system"] = system

        return payload

    def transform_response(self, raw) -> dict:
        return {
            "content": raw["content"][0]["text"],
            "model": raw["model"],
            "provider": "anthropic",
            "usage": {
                "prompt_tokens": raw["usage"]["input_tokens"],
                "completion_tokens": raw["usage"]["output_tokens"],
                "total_tokens": raw["usage"]["input_tokens"] + raw["usage"]["output_tokens"]
            }
        }

    def chat(self, messages, model, api_key, **kwargs):
        payload = self.transform_request(messages, model, **kwargs)
        r = httpx.post(
            self.BASE_URL,
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": self.API_VERSION,
                "content-type": "application/json"
            },
            timeout=60
        )
        r.raise_for_status()
        return self.transform_response(r.json())
```

### Common Anthropic models to support

| Model String | Notes |
|---|---|
| `claude-3-5-sonnet-20241022` | Best overall |
| `claude-3-5-haiku-20241022` | Fast and cheap |
| `claude-3-opus-20240229` | Most capable |

---

## 7. Phase 4 — Add Gemini Provider

Gemini uses Google's own format. Biggest difference: messages use `parts` array instead of a `content` string.

### providers/gemini.py

```python
import httpx
from base import BaseProvider

class GeminiProvider(BaseProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def transform_request(self, messages, model, **kwargs):
        contents = []
        for m in messages:
            if m["role"] == "system":
                continue  # handled separately
            role = "user" if m["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m["content"]}]
            })

        system = next(
            (m["content"] for m in messages if m["role"] == "system"),
            None
        )

        payload = {"contents": contents}
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}

        return payload

    def transform_response(self, raw) -> dict:
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        usage = raw.get("usageMetadata", {})
        return {
            "content": text,
            "model": raw.get("modelVersion", "gemini"),
            "provider": "gemini",
            "usage": {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0)
            }
        }

    def chat(self, messages, model, api_key, **kwargs):
        payload = self.transform_request(messages, model, **kwargs)
        url = self.BASE_URL.format(model=model)
        r = httpx.post(
            url,
            json=payload,
            params={"key": api_key},
            timeout=60
        )
        r.raise_for_status()
        return self.transform_response(r.json())
```

### Common Gemini models to support

| Model String | Notes |
|---|---|
| `gemini-1.5-pro` | Best overall |
| `gemini-1.5-flash` | Fast and cheap |
| `gemini-2.0-flash-exp` | Experimental, fast |

---

## 8. Streaming

Streaming returns chunks in real-time instead of waiting for the full response. All providers support SSE (Server-Sent Events) but emit them in different formats. The goal is to normalize all of them into one consistent SSE output.

### 8.1 Normalized streaming output format

Regardless of provider, your `/chat/stream` endpoint always emits:

```
data: Hello
data:  there
data: !
data: [DONE]
```

### 8.2 FastAPI streaming endpoint

```python
from fastapi.responses import StreamingResponse

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    provider = get_provider(req.provider)
    return StreamingResponse(
        provider.stream(req.messages, req.model, req.api_key),
        media_type="text/event-stream"
    )
```

### 8.3 OpenAI / NIM streaming (same format)

```python
async def stream(self, messages, model, api_key, **kwargs):
    payload = self.transform_request(messages, model, **kwargs)
    payload["stream"] = True

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", self.BASE_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60
        ) as r:
            async for line in r.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    data = json.loads(line[6:])
                    delta = data["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield f"data: {delta}\n\n"
    yield "data: [DONE]\n\n"
```

### 8.4 Anthropic streaming

```python
async def stream(self, messages, model, api_key, **kwargs):
    payload = self.transform_request(messages, model, **kwargs)
    payload["stream"] = True

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", self.BASE_URL,
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": self.API_VERSION
            },
            timeout=60
        ) as r:
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "content_block_delta":
                        text = data["delta"].get("text", "")
                        if text:
                            yield f"data: {text}\n\n"
    yield "data: [DONE]\n\n"
```

---

## 9. Error Handling

### 9.1 schemas.py

```python
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    messages: list
    stream: bool = False
    max_tokens: Optional[int] = 1024

class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str
    usage: dict
```

### 9.2 Error types to handle

| Error | HTTP Status | When |
|---|---|---|
| Unknown provider | 400 | `provider` not in PROVIDERS dict |
| Invalid API key | 401 | Provider returns 401/403 |
| Rate limit hit | 429 | Provider returns 429 |
| Model not found | 404 | Wrong model string passed |
| Provider timeout | 504 | Request takes too long |
| Provider server error | 502 | Provider returns 500 |

### 9.3 Error handler in main.py

```python
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        provider = get_provider(req.provider)
        return provider.chat(req.messages, req.model, req.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid API key")
        elif e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        else:
            raise HTTPException(status_code=502, detail="Provider error")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
```

---

## 10. Frontend Integration

### 10.1 ProviderSelector.tsx

```tsx
const PROVIDERS = [
  { value: "nvidia", label: "Nvidia NIM" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Google Gemini" },
]

const MODELS: Record<string, string[]> = {
  nvidia: ["meta/llama-3.1-8b-instruct", "mistralai/mixtral-8x7b-instruct-v0.1"],
  openai: ["gpt-4o", "gpt-4o-mini"],
  anthropic: ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
  gemini: ["gemini-1.5-pro", "gemini-1.5-flash"],
}

export function ProviderSelector({ onSelect }) {
  const [provider, setProvider] = useState("openai")
  const [model, setModel] = useState(MODELS["openai"][0])

  return (
    <div>
      <select onChange={e => {
        setProvider(e.target.value)
        setModel(MODELS[e.target.value][0])
        onSelect({ provider: e.target.value, model: MODELS[e.target.value][0] })
      }}>
        {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
      </select>

      <select value={model} onChange={e => {
        setModel(e.target.value)
        onSelect({ provider, model: e.target.value })
      }}>
        {MODELS[provider].map(m => <option key={m} value={m}>{m}</option>)}
      </select>
    </div>
  )
}
```

### 10.2 ApiKeyInput.tsx

```tsx
export function ApiKeyInput({ onChange }) {
  return (
    <input
      type="password"
      placeholder="Enter your API key"
      onChange={e => onChange(e.target.value)}
    />
  )
}
```

Keys are never stored — passed per request only, held in component state.

### 10.3 lib/api.ts

```ts
export async function sendMessage({
  provider,
  apiKey,
  model,
  messages,
}: {
  provider: string
  apiKey: string
  model: string
  messages: { role: string; content: string }[]
}) {
  const res = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider,
      api_key: apiKey,
      model,
      messages,
    }),
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || "Request failed")
  }

  return res.json()
}
```

---

## 11. API Contract

### POST /chat — Non-streaming

**Request:**
```json
{
  "provider": "openai",
  "api_key": "sk-...",
  "model": "gpt-4o",
  "messages": [
    { "role": "system", "content": "You are helpful." },
    { "role": "user", "content": "Hello" }
  ],
  "stream": false
}
```

**Success Response (200):**
```json
{
  "content": "Hello! How can I help?",
  "model": "gpt-4o",
  "provider": "openai",
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 7,
    "total_tokens": 22
  }
}
```

**Error Response:**
```json
{
  "detail": "Invalid API key"
}
```

### POST /chat/stream — Streaming

Same request body. Returns `text/event-stream`:

```
data: Hello
data: !
data:  How
data:  can
data:  I
data:  help?
data: [DONE]
```

---

## 12. Verifiable Milestones

Complete each milestone before moving to the next. Each is independently testable with curl.

### Milestone 1 — NIM adapter works (no behavior change)
- Wrap NIM in `NimProvider` class
- `/chat` with `"provider": "nvidia"` returns same result as before
- **Test:** curl with real NIM key, compare output to pre-refactor

### Milestone 2 — OpenAI works
- `/chat` with `"provider": "openai"` returns normalized response
- **Test:** curl with real OpenAI key
- **Error test:** wrong key returns `401 Invalid API key`

### Milestone 3 — Anthropic works
- `/chat` with `"provider": "anthropic"` returns normalized response
- System prompt correctly extracted and sent separately
- **Test:** curl with real Anthropic key

### Milestone 4 — Gemini works
- `/chat` with `"provider": "gemini"` returns normalized response
- **Test:** curl with real Gemini key

### Milestone 5 — Streaming works for all providers
- `/chat/stream` returns SSE chunks for all 4 providers
- Frontend receives and renders tokens in real time

### Milestone 6 — Frontend connected
- Provider dropdown renders all 4 options
- Model dropdown updates based on selected provider
- API key input masked
- Chat sends request, renders response

### Milestone 7 — Error states handled in UI
- Wrong key → user sees "Invalid API key"
- Rate limit → user sees "Rate limit exceeded, try again"
- Unknown model → user sees clean error, not a blank screen

---

## 13. What NOT to Build Yet

Avoid these until all milestones above are done. They add complexity without validating the core.

| Feature | Why skip for now |
|---|---|
| Key storage / encryption | BYOK passthrough is enough for MVP |
| Usage tracking / dashboards | Add after all providers work |
| Auth / user accounts | Not needed to validate the gateway |
| Cost calculation | Needs usage tracking first |
| Response caching | Premature optimization |
| Rate limiting on your end | Providers handle this for now |
| More than 4 providers | Validate the pattern with 4 first |
| Model auto-routing (cheapest/fastest) | Advanced feature, add later |

---

*Stack: FastAPI · Next.js · httpx · Pydantic*  
*Starting point: Nvidia NIM already integrated*  
*Pattern reference: aisuite (github.com/andrewyng/aisuite)*
