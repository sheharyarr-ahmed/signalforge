---
name: hf-inference-client
description: Correct 2026 Hugging Face Inference Providers API usage for SignalForge — router endpoints, payload shapes, auth, and the four-class error contract. Use before writing or changing any code that calls the HF API (hf_client.py, sentiment.py, classifier.py).
---

# HF Inference Providers client (verified 2026-07)

## Endpoint — the old host is dead

`api-inference.huggingface.co` no longer resolves in DNS. Everything goes through Inference Providers:

```
POST https://router.huggingface.co/hf-inference/models/{model_id}
Authorization: Bearer <HF_API_TOKEN>
Content-Type: application/json
```

Both locked models are live and warm on the `hf-inference` provider (their **only** provider — pin it, never use provider auto-routing):
- `cardiffnlp/twitter-xlm-roberta-base-sentiment` — task `text-classification`
- `facebook/bart-large-mnli` — task `zero-shot-classification`

Token: fine-grained with "Make calls to Inference Providers" permission, or a classic read token. Invalid token → 401 `{"error": "Invalid username or password."}`.

## Payloads and responses

Text classification:
```json
{"inputs": "Este producto es increíble"}
```
Zero-shot (candidate_labels is required):
```json
{"inputs": "The party of the first part…", "parameters": {"candidate_labels": ["legal", "financial", "marketing", "technical"], "multi_label": false}}
```
Both return an array of `{"label": str, "score": float}` (text-classification may nest one level: `[[{...}]]` — normalize before parsing).

## Error contract (four-class, see rules/error-handling.md)

| Status | Meaning | Route |
|---|---|---|
| 402 | Monthly credits exhausted (free tier = **$0.10/month**, compute-billed) | `HFQuotaError` → local fallback; cache exhausted state until month rollover |
| 429 | Rate limit, 5-minute fixed windows; `RateLimit` headers carry reset seconds | `HFRateLimitError` → local fallback, no retry |
| 503/5xx | Transient server error. The old `503 + estimated_time` cold-start contract is **defunct** — do not parse `estimated_time`, do not wait-for-model | `HFTransientError` → retry exactly once (250 ms) |
| timeout > 10 s | — | `HFTimeoutError` → local fallback, no retry |

## Implementation choice

Use **raw async httpx** against the router URL — the four-class routing needs direct status-code access, and this is the decision to defend in interviews (`huggingface_hub.AsyncInferenceClient` exists and is fine, but it wraps errors in `HfHubHTTPError`/`InferenceTimeoutError` and hides status granularity behind its own retry/normalization layer).

```python
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.post(
        f"https://router.huggingface.co/hf-inference/models/{model_id}",
        headers={"Authorization": f"Bearer {settings.hf_api_token}"},
        json=payload,
    )
```

Never build a client per request in production code — one module-level `AsyncClient` reused across calls.
