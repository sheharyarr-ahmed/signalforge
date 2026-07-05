# Architecture

## Request flow

```
Client (curl/SDK)
    ↓ HTTP
FastAPI router
    ↓ (route by path)
Handler (thin; validates input schema)
    ↓ (pass to service layer)
Service layer (orchestration, timing, metadata assembly)
    ├─ HF Inference API call (sentiment, classify)
    │  ├─ 402 (quota) → HFQuotaError
    │  ├─ 429 (rate limit) → HFRateLimitError
    │  ├─ 503/5xx (transient) → HFTransientError (retryable)
    │  └─ >10s timeout → HFTimeoutError
    ├─ Local CPU model (sentiment fallback)
    │  └─ sentence-transformers / transformers
    ├─ Local CPU model (embeddings only)
    │  └─ sentence-transformers/all-MiniLM-L6-v2
    └─ Supabase pgvector
       └─ RPC query (cosine similarity search)
    ↓
InferenceMetadata assembly
    ├─ model (full HF repo ID)
    ├─ provider ("huggingface_api" or "local")
    ├─ processing_time_ms
    ├─ fallback_triggered (bool)
    └─ confidence (float | null)
    ↓
Response schema (SentimentResponse, ClassifyResponse, EmbedResponse, SearchResponse)
    ↓ JSON
Client
```

## Error handling rationale

**Why a four-class taxonomy instead of a catch-all?**

A single `except Exception` around HF calls creates two failure modes:
1. **Hamming a cold-starting model:** the spec's original D3 (retry on 503 with `estimated_time`) is correct in principle, but the live HF Inference Providers now serve warm models — retrying transient errors is safe, but you must not retry quota (402) or rate-limit (429) exhaustion; doing so burns the $0.10/month credit pool on a single demo request.
2. **Giving up on recoverable calls:** timeout (>10 s) is recoverable for sentiment (local fallback exists) but not for classify (no 1.6 GB local bart-large-mnli). A catch-all either retries both (wasteful) or falls back for both (incorrect).

**Per-class routing:**

- **402 Quota exhausted** (`HFQuotaError`): cache the exhausted state in-process and fall back to local until month rollover. Never re-hit the API in the same request. Classify: return honest HTTP 503 (no local model).
- **429 Rate limit** (`HFRateLimitError`): immediate local fallback, no retry. The 5-minute window will clear. Classify: return HTTP 503.
- **503/5xx Transient error** (`HFTransientError`): retry exactly once with 250 ms backoff. Bounded at 2 total attempts. Classify: if retry fails, return HTTP 503.
- **>10s timeout** (`HFTimeoutError`): immediate local fallback, no retry. The caller's network or the endpoint is unstable; retrying will likely timeout again. Classify: return HTTP 503.

This is the discipline that keeps a $0-budget public demo alive.

## Why sentiment has dual paths and classify doesn't

**Sentiment** (`cardiffnlp/twitter-xlm-roberta-base-sentiment`, ~1.04 GiB):
- Hosted on HF Inference API (authoritative, multi-language tuning on HF's hardware, ~100–500 ms latency).
- Local fallback: the same 1.04 GiB model, lazy-loaded once into memory, runs on CPU for inference if the API fails (402, 429, timeout, or 503 after one retry). Local inference takes ~100–200 ms on CPU.
- This asymmetry is intentional: demonstrate the hosted API (the skill clients hire for), but guarantee the demo survives quota exhaustion (the portfolio's differentiator).

**Classify** (`facebook/bart-large-mnli`, API-only):
- Hosted on HF Inference API only. No local fallback.
- Rationale: bart-large-mnli is 1.6 GB, and loading it alongside the 1.04 GB sentiment model would exceed memory budgets on the deployment target (Hugging Face Spaces free tier has 16 GB, which is safe; Render free tier has 512 MB, which is not). By design, classify requires the hosted API.
- Error contract: every error class (402, 429, 503, timeout) terminates in an honest HTTP 503 `ErrorResponse` describing the failure. No silent degradation.

## The vector column is locked at 384 dimensions

**Why 384?**
- Standard for `sentence-transformers/all-MiniLM-L6-v2`, the industry-standard free embedding.
- Matches Supabase's example pgvector schemas.
- 384 floats × 4 bytes = 1536 bytes per embedding — memory-friendly at scale.

**Why a lock (one-way door)?**
- Changing dimensionality after deployment means:
  - All existing vectors in Supabase become invalid (wrong shape).
  - Re-embedding the entire corpus with the new model.
  - Rebuilding the HNSW index.
  - Zero downtime if using the RPC layer (new query embedding in new space, old documents queried against new index).
- This is a production decision: once data is in the database, the embedding dimension is immutable. Locking it in the spec prevents a mid-project pivot that costs a full re-run.

## Inference metadata: the traceability discipline

Every response from every endpoint carries `inference_metadata`:

```json
{
  "model": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
  "provider": "huggingface_api",
  "processing_time_ms": 412,
  "fallback_triggered": false,
  "confidence": 0.97
}
```

**Why?** An NLP endpoint without traceability is not defensible in production:
- **`model`**: always the full HF repo ID, never a short name or alias. Auditable.
- **`provider`**: exactly `"huggingface_api"` or `"local"` — tells you which path served the request. If local, you know the API failed and the fallback was triggered.
- **`processing_time_ms`**: request latency. Customers see cold-start blips; this field explains them.
- **`fallback_triggered`**: boolean. If true, the API failed and local inference ran. For classify, never true (no local model).
- **`confidence`**: top-label score for sentiment and classify (the model's certainty in the answer). For embed/search, `null` (embeddings have no confidence, only similarity scores).

This is the portfolio's equivalent of AuditDoc's mandatory source citations. The field name is `inference_metadata`, not "citations" — AuditDoc owns that vocabulary, SignalForge owns this one.

## Supabase pgvector and the RPC layer

**Direct Postgres is unavailable from Hugging Face Spaces.** The deployment environment restricts outbound traffic to HTTP (80), HTTPS (443), and custom ports (8080+). Direct Postgres (port 5432) is blocked.

**Solution:** Supabase's PostgREST layer (HTTPS) exposes the `match_documents(query_embedding vector(384), match_count int)` function as an RPC endpoint. The embedder service calls this via `supabase.rpc("match_documents", {...})`.

**Index:** HNSW (Hierarchical Navigable Small Worlds) instead of ivfflat:
- ivfflat requires pre-existing rows to train centroids. On an empty table (as during Phase 1 deployment), it produces a degenerate index.
- HNSW builds incrementally as rows are inserted; no training phase.
- Both use `vector_cosine_ops` for cosine-distance similarity, which is the standard for semantic search.

## Locked decisions summary

| Decision | Ruling | Trade-off |
|----------|--------|-----------|
| **D1** | HF Spaces (Docker, CPU basic) is mandatory | 48 h sleep (vs. 15 min on Render free) requires keep-alive; Render free (512 MB) cannot fit the local sentiment fallback (~1.1–1.5 GB loaded). |
| **D2** | HF Inference API + local CPU fallback | Demonstrates hosted API skill; guarantees demo survives quota exhaustion. |
| **D3** | Four-class error routing (402/429/503/timeout) | Prevents both hammering and silent degradation. |
| **D4** | Bounded retry: max 2 attempts, 250 ms, transient class only | Protects the $0.10/month free-tier credit pool from runaway retry storms. |
| **D5** | Three models locked: sentiment (dual-path), classify (API-only), embeddings (local-only) | Asymmetry is deliberate: classify requires too much RAM to run locally; sentiment justifies both paths. |
| **D6** | pgvector(384) with HNSW index | 384-dim standard for all-MiniLM; HNSW incremental on empty table. One-way door: changing dimensionality requires re-embedding everything. |
| **D7** | `inference_metadata` on every response | Traceability and auditability: which model served it? Did it fall back? How confident was the answer? |
| **D8** | Pydantic v2 strict mode at every boundary | No implicit coercion, no `Any` types. Field constraints in schemas, not handler code. |
| **D9** | structlog JSON logging from day one | Observability for debugging and demo walkthroughs. |
| **D10** | Zero AI attribution (mechanically enforced) | Contributor graph shows one author. Git hook rejects "Claude"/"Anthropic"/"Co-Authored-By". |
| **D14** | Anti-fabrication walls (SPEC.md locked claims only) | Defensible in interviews: production NLP pipeline, multi-language sentiment, zero-shot classification, local embeddings, pgvector search, cost-optimization. Forbidden: custom training, fine-tuning, GPU inference, production scale. |

## Web-verified amendments (SPEC-AMENDMENTS.md)

**A1 — API host correction:** `api-inference.huggingface.co` is dead. The successor is `router.huggingface.co/hf-inference/models/{model_id}`. Both locked models live and warm on `hf-inference`.

**A2 — Four-class error taxonomy (not three):** Free tier is now a $0.10/month credit pool; exhaustion returns **HTTP 402**, not 503. The old cold-start contract (`503 + estimated_time` header) is defunct; hf-inference serves warm models. New routing added: 402 → quota error (local fallback, in-process cache until month rollover).

**A3 — Two-step backoff is unreachable:** Max-2-attempts means exactly one backoff interval. Backoff delay: 250 ms, capped at 1 s. "Exponential" language dropped; only transient (5xx) class retries at all.

**A4 — Sentiment model is 1.04 GiB, not 80 MB:** Render free (512 MB) cannot host the full stack with local sentiment fallback. **Spaces is mandatory, not preferred.** The only degraded mode on Render would be embeddings-only without local fallback — documented in SCALING.md, not built.

**A5 — ivfflat → HNSW:** pgvector index must use HNSW (builds incrementally on empty table). ivfflat requires pre-existing rows for training. Additionally, migrations must define the `match_documents(query_embedding vector(384), match_count int)` RPC function (PostgREST exposes no direct pgvector operators).

**A6 — Dockerfile contracts:** Spaces container runs as UID 1000 non-root; app listens on 0.0.0.0:7860; models downloaded at image build time; ephemeral disk; outbound traffic restricted to 80/443/8080 (Supabase HTTPS only, no direct Postgres); Torch installed from CPU wheels first.

**A7 — Supabase free pauses after ~7 idle days:** Manual dashboard resume required. Paused >90 days → restorable via backup download only. Demo-day runbook: (a) resume if paused, (b) ping Space URL (~1 min cold wake), (c) run five-curl verification block. GitHub Actions keep-alive ping (`.github/workflows/keepalive.yml`) mitigates both Space sleep and Supabase pause ($0).

**A10 — `confidence` field clarification:** Float for sentiment/classify (top-label score), `null` for embed/search (no confidence, only similarity). Model name always full HF repo ID (e.g., `sentence-transformers/all-MiniLM-L6-v2`).
