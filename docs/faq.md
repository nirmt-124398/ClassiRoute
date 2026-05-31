# Frequently Asked Questions — ClassiRoute

## General

### What is ClassiRoute?

ClassiRoute is an ML-powered LLM routing engine. It classifies every incoming prompt by complexity and routes it to the cheapest model tier that can handle it adequately. Think of it as an intelligent proxy that sits between your application and your LLM providers, making real-time model selection decisions.

It's built around an XGBoost classifier (~92% accuracy) that predicts prompt difficulty from features like length, domain, instruction complexity, and semantic embedding. When confidence is low, it cascades up through increasingly capable (and expensive) models until requirements are met.

### How is ClassiRoute different from LiteLLM?

**LiteLLM** provides a unified API interface for multiple LLM providers — it's the "plumbing" layer. It handles authentication normalization, provider switching, and request translation so you write once and call any model.

**ClassiRoute** sits *on top* of that plumbing and adds the "intelligence" layer: ML-based classification, automatic cost optimization, cascading fallback on failure, and an analytics dashboard showing every routing decision and its cost impact.

| Capability | LiteLLM | ClassiRoute |
|---|---|---|
| Unified provider API | ✅ | ✅ |
| Model routing | Manual (you pick) | Automatic (ML-picked) |
| Cost optimization | You manage | Built-in, ~58% avg savings |
| Fallback logic | Configurable | Cascading + confidence-based |
| Dashboard / analytics | ❌ | ✅ |
| Provider failover | Basic | Cascading tier-to-provider |
| Pre-trained classifiers | ❌ | ✅ |

**In short:** LiteLLM standardizes *access* to models. ClassiRoute optimizes *which* model to use and *when*.

### How is ClassiRoute different from OpenRouter?

OpenRouter is a hosted proxy that provides unified billing and access to many models. You pay OpenRouter, they handle provider relationships.

ClassiRoute is designed to be self-hosted (or hosted by you) with your own API keys. It focuses on classification and optimization rather than billing aggregation. You can run it inside your VPC with no external dependencies, keeping all prompt data and keys under your control.

### How is it different from other routing proxies (e.g., ML-in-a-box, simple fallback chains)?

Most routing proxies use hardcoded rules: "if prompt length < 100 tokens, use cheap model." These rules are brittle, don't generalize, and require constant maintenance as usage patterns shift.

ClassiRoute uses a trained ML classifier that learns from actual routing outcomes. It considers multiple features simultaneously — semantic content, instruction density, domain, token length, and more — and adapts as you retrain on your own data. The result is more nuanced decisions that simple length or keyword heuristics miss.

---

## Classification & Accuracy

### Do I need to train my own model?

**No.** ClassiRoute ships with pretrained models that work out of the box. The default model achieves ~92% accuracy on a general-purpose benchmark spanning summarization, Q&A, code generation, creative writing, and classification tasks.

If your workload is highly domain-specific (e.g., medical diagnosis, legal document analysis), you can fine-tune on your own prompt→model traces. ClassiRoute includes a training pipeline and retraining API for this purpose.

### What happens if the ML classifier is wrong?

ClassiRoute uses a multi-layer safety net:

1. **Confidence thresholding** — The classifier outputs a confidence score for each prediction. If confidence is below a configurable threshold (default: 0.7), the request is automatically upgraded to the next tier instead of using the raw prediction.
2. **Cascading retry** — If the selected model returns low-quality output (detected via response heuristics like repetition, refusal patterns, or very short output), ClassiRoute automatically retries with the next tier up. Retries are transparent to the caller.
3. **Override header** — You can force a specific model per request via the `X-ClassiRoute-Force-Model` header, bypassing the classifier entirely.
4. **Per-request confidence telemetry** — Every decision is logged with confidence, tier chosen, and actual model used. You can audit and adjust thresholds based on real data.

In practice, the combination of confidence gating and cascading retry means accuracy *floor* is much higher than the raw classifier — quality parity with always-using-the-best-model is 96.8%.

### How does the classifier work under the hood?

The pipeline:

1. **Feature extraction** — Prompt length, stopword frequency, instruction density, domain classification (via lightweight BERT embedding), presence of code blocks, question type indicators.
2. **Embedding** — A small SentenceTransformer model produces a 384-dimension embedding of the prompt.
3. **Classification** — An XGBoost model (~200 trees, max depth 6) classifies into one of three tiers: **simple** (cheap model), **moderate** (mid-range), **complex** (strongest model).
4. **Confidence scoring** — Class probabilities from the softmax of tree outputs provide a calibrated confidence estimate.

Total inference latency: ~15–40ms on CPU, ~5–15ms with GPU.

### Can I see why a particular route was chosen?

Yes. Set the `X-ClassiRoute-Debug` header to `true` on any request, and the response headers include:

```
X-ClassiRoute-Tier: moderate
X-ClassiRoute-Confidence: 0.83
X-ClassiRoute-Model: claude-sonnet-4
X-ClassiRoute-Fallback: false
X-ClassiRoute-Latency: 32ms
```

The analytics dashboard also shows feature breakdowns for each routing decision.

---

## Providers & Keys

### Can I use my own provider API keys?

**Yes.** You bring your own keys. They are stored encrypted at rest (Fernet symmetric encryption) in the database and decrypted in-memory only when a request needs to be dispatched to a provider.

Keys are managed through the dashboard or the `/api/v1/keys` API — you can add, rotate, or revoke keys without downtime. No provider keys are ever logged or exposed in responses.

### What providers are supported?

| Provider | Supported | Adapter |
|---|---|---|
| OpenAI / OpenAI-compatible | ✅ | Native (Chat Completions API) |
| Anthropic (Claude) | ✅ | Built-in adapter |
| Google Gemini | ✅ | Built-in adapter |
| Any OpenAI-compatible endpoint | ✅ | Generic adapter (set base URL) |
| Azure OpenAI | ✅ | Via OpenAI-compatible adapter |
| AWS Bedrock | 🔄 Roadmap | |
| Together AI / Fireworks / Groq | ✅ | Via OpenAI-compatible adapter |

The provider adapter system is extensible — see [multi-provider-adapters.md](./multi-provider-adapters.md) for the interface spec.

### Can I add a custom provider not listed here?

Yes. Implement the `ProviderAdapter` interface (a single class with `complete()` and `complete_stream()` methods) and register it in config. See the [implementation guide](./implementation-guide.md) for examples.

---

## Streaming & API

### Does ClassiRoute support streaming?

**Yes.** SSE (Server-Sent Events) streaming with OpenAI-compatible chunk formats. When the upstream provider streams tokens, ClassiRoute transparently proxies them to your client with the same chunk structure your application already expects.

The classifier runs before streaming begins (it only needs the prompt text), so there is no added streaming latency — classification adds ~15–40ms upfront, then the stream proceeds at normal speed.

### How do I integrate with my existing app?

**Minimal change** — update the base URL in your LLM client configuration:

```python
# Before: direct to provider
client = OpenAI(api_key="sk-...", base_url="https://api.openai.com/v1")

# After: through ClassiRoute
client = OpenAI(api_key="<your-virtual-key>", base_url="https://classiroute.example.com/v1")
```

All OpenAI-compatible SDKs, LangChain, LlamaIndex, and other tools work out of the box. No code changes beyond the URL and key swap.

If you need more control, ClassiRoute also exposes a native REST API at `/api/v1/route` with additional features like confidence scores, model override, and debug headers.

### Is there rate limiting?

ClassiRoute has configurable per-key rate limiting (default: 60 RPM). Rate limits are tracked per virtual key, not per upstream provider. You can configure tiers of keys with different rate limits in the dashboard.

Upstream provider rate limits are handled by the adapters, which include configurable retry and backoff.

---

## Cost & Performance

### How much does it save?

On the default configuration with a mix of general-purpose prompts, ClassiRoute achieves a **57.9% average cost reduction** compared to routing everything to the strongest available model (GPT-4o or Claude Opus).

Breakdown by tier:

| Tier | % of traffic | Cost per 1M tokens (in) | Cost per 1M tokens (out) |
|---|---|---|---|
| Simple | ~55% | $0.15 | $0.60 |
| Moderate | ~30% | $3.00 | $15.00 |
| Complex | ~15% | $15.00 | $75.00 |

Savings vary by workload. Code-heavy or reasoning-heavy traffic shifts distribution toward higher tiers. Simple Q&A or summarization-heavy traffic saves more. The dashboard provides real-time cost tracking per project, key, and model.

### What is the latency overhead?

- **Classifier inference**: 15–40ms CPU, 5–15ms GPU
- **Request proxying**: <2ms added per hop (FastAPI in-process proxy)
- **Streaming**: Zero added per-token latency (transparent passthrough after initial classification)

Total median overhead: ~25ms per request.

### Does the classifier cache results?

Yes. ClassiRoute caches classification results by prompt hash (SHA-256 of normalized prompt text). TTL is configurable (default: 1 hour). If the same prompt is submitted again, the routing decision is served from cache in <1ms, bypassing the ML pipeline entirely.

The cache is especially effective for system prompts, evaluation harnesses, and batched workloads.

---

## Production & Reliability

### Is it production-ready?

ClassiRoute is in **beta** stage. It is deployed and serving production traffic in several environments, with a full test suite (unit + integration + load tests). The core routing pipeline is stable.

Current beta considerations:
- The dashboard UI is actively evolving (new charts and filters per release)
- Provider adapter API is stable but may gain minor convenience methods
- The training pipeline is functional but the CLI ergonomics are still rough

### What happens if a provider is down?

ClassiRoute implements **cascading fallback**. If the chosen provider returns a 5xx error, rate-limit response, or timeout:

1. The request is retried (configurable: default 1 retry, 500ms backoff)
2. On failure, the adapter falls back to the next available provider for the same tier
3. If no provider is available for the tier, it escalates to the next higher tier
4. If all tiers and providers are exhausted, a 503 is returned with diagnostics

Fallback chains are fully configurable per deployment.

### Can I self-host?

**Yes.** ClassiRoute ships with a `docker-compose.yml` that starts everything:
- FastAPI backend with the classifier
- React dashboard
- PostgreSQL (for virtual keys, routing logs, analytics data)
- Redis (for classification cache and rate limiting)

```bash
git clone <repo>
docker compose up -d
```

No external service dependencies. Everything runs in your infrastructure. See [deployment.md](./deployment.md) for production considerations (scaling, secrets management, monitoring).

### What about high availability?

ClassiRoute is stateless from the routing perspective (state lives in PostgreSQL and Redis). You can run multiple backend replicas behind a load balancer:

- **Horizontal scaling**: Add replicas, classifier is CPU-only and scales linearly
- **Database**: Use managed PostgreSQL (RDS, Cloud SQL) for HA
- **Cache**: Redis Sentinel or Cluster for cache HA
- **Health checks**: `/health` endpoint returns 200 when all subsystems are ready

### Is there a hosted version?

Not yet. Self-hosted only for now. A managed cloud offering is on the roadmap — [let us know](mailto:hello@classiroute.dev) if you're interested.

---

## Security

### How are my API keys stored?

API keys are encrypted at rest using **Fernet symmetric encryption** (AES-128-CBC with HMAC-SHA256, via the `cryptography` library). The encryption key is provided via the `CLASSIROUTE_ENCRYPTION_KEY` environment variable.

- Keys are decrypted **in-memory only** when a request is being dispatched
- Decrypted keys are never written to disk, logs, or the database
- Key access is audited (each decryption is logged with a timestamp and routing context)
- You can rotate the encryption key and re-encrypt all stored keys via the management CLI

### Is prompt data logged or stored?

By default:
- Prompt **text** is never stored persistently
- Prompt **metadata** (length, token count, domain classification, selected tier) is logged for analytics
- Full response **tokens** and **latency** are logged for cost tracking
- You can enable full prompt logging per virtual key (off by default, requires explicit opt-in)

Prompts pass through ClassiRoute in-transit to the upstream provider and are not retained unless logging is enabled.

### Can I run ClassiRoute entirely on-prem / air-gapped?

Yes. The only outbound connections are to configured LLM provider APIs. No telemetry, no license check, no external model downloads at runtime (models are bundled in the Docker image). Database, cache, and dashboard are all self-contained.

---

## Model Management

### Can I customize which models are available per tier?

Yes. The model tier configuration is a YAML/JSON file that maps tiers to model+provider combinations:

```yaml
tiers:
  simple:
    - provider: openai
      model: gpt-4o-mini
    - provider: anthropic
      model: claude-haiku-4
  moderate:
    - provider: openai
      model: gpt-4o
    - provider: anthropic
      model: claude-sonnet-4
  complex:
    - provider: openai
      model: gpt-4o-with-reasoning
    - provider: anthropic
      model: claude-opus-4
    - provider: gemini
      model: gemini-2.5-pro
```

You can add, remove, or reorder models per tier. Add failover models, use different providers per tier, or flatten to a single tier if you only want the proxy features.

### How do I add a new model that isn't in the default list?

If the provider is already supported, you just add the model name to the tier config and ensure your provider key has access. ClassiRoute validates model availability on startup (optional, can be skipped).

For a new provider, implement the `ProviderAdapter` interface — it's about 50 lines of code for basic support.

### What happens to routing when a model is deprecated or removed?

If an upstream provider deprecates a model, requests to that model will fail. The cascading fallback system handles this — on failure, it moves to the next model in the tier's priority list. You can then update the tier configuration to remove the deprecated model without any downtime.

---

## Troubleshooting

### Why is every request going to the complex tier?

Most common causes:
1. **No classifier model loaded** — Check backend logs for `Model not loaded, defaulting to highest tier`
2. **Confidence threshold too high** — Default is 0.7; try lowering to 0.6
3. **Feature extraction failing** — Check that the embedding model is accessible
4. **All lower-tier providers are misconfigured** — Verify API keys for cheap-tier models

Run `curl /api/v1/admin/classifier-status` to check the classifier's state.

### How do I bypass the classifier for a specific request?

Use the `X-ClassiRoute-Force-Model` header:

```bash
curl -X POST https://classiroute.example.com/v1/chat/completions \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -H "X-ClassiRoute-Force-Model: gpt-4o" \
  -d '{"model": "gpt-4o-mini", "messages": [...]}'
```

This bypasses classification entirely and sends directly to the specified model. The `model` field in the request body is still used as a fallback identifier, but the header takes precedence.

### How do I reset or regenerate a virtual key?

Dashboard → Keys → Click the key → "Regenerate". The old key is immediately invalidated. You can also use the API:

```bash
POST /api/v1/keys/<key-id>/regenerate
```

### I found a bug, how do I report it?

Open an issue on the GitHub repository with:
- Backend logs (sanitized)
- The request payload (redact sensitive data)
- Expected vs actual behavior
- Classifier debug output (`X-ClassiRoute-Debug: true`)

---

## Still have questions?

Open a [GitHub Discussion](https://github.com/your-org/classiroute/discussions) or email **hello@classiroute.dev**.
