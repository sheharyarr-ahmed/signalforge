# Scaling — honest free-tier limits and the production upgrade path

SignalForge is built on $0 infrastructure (Hugging Face Spaces free, Supabase free). This page discloses exactly what breaks at what load, when, and the concrete paid upgrade that fixes each limit.

## Free-tier limits (honest disclosure)

### Hugging Face Space sleep (48 h inactivity)

**What breaks:** The Space container suspends and deallocates after ~48 hours of no traffic. First request after wake triggers a ~1-minute cold start.

**Impact:** 
- Live demo link in a proposal requires a wake-up ritual before showing it.
- Overnight demos or end-of-week recordings fail silently if the Space slept during production.

**Mitigation:** `.github/workflows/keepalive.yml` pings `/health` + `/api/v1/search` daily (keeps the Space awake at $0).

**Production upgrade:**
- **Hugging Face Inference Endpoints** (dedicated): $9–15/month for always-on, cold-start latency → ~50 ms.
- **Alternative:** self-hosted on Railway, Render paid, AWS Lightsail ($5–20/month).

---

### Hugging Face Inference API free quota ($0.10/month credits)

**What breaks:** Each call to the sentiment or classify endpoint consumes credits from a global $0.10/month pool. Exhaustion returns HTTP 402 (quota error) mid-month.

**Impact:**
- Sentiment falls back to local (~100–200 ms on CPU, reliable).
- Classify has no local model (1.6 GB makes it infeasible) → returns an honest HTTP 503 `ErrorResponse` (`{error, error_class}`, e.g. `error_class: "HFQuotaError"`). No fallback occurs; `fallback_triggered` never becomes true for classify.
- After exhaustion, all HF Inference API calls fail until the pool resets (monthly, not monthly per endpoint).

**Your quota burn rate:**
- Sentiment via API: ~0.00001 credits per call (negligible).
- Classify via API: ~0.0005 credits per call (higher).
- 10 demos/day of all endpoints (sentiment + classify + embed + search): ~$0.0015/month (well under $0.10, sustainable).
- 1000 calls/day of all endpoints: ~$0.15/month (exceeds quota by mid-month).

**Mitigation:**
- Sentiment: local fallback absorbs quota exhaustion (customers don't see it).
- Classify: be aware of your demo frequency. A 5-minute demo walkthrough (sentiment + classify + embed search sequence repeated twice) costs ~0.001 credits. $0.10 = 100 walkthrough-equivalents per month = ~3 per day, sustainable.

**Production upgrade:**
- **HF Inference Endpoints Prepaid Credits:** $10/month = $1 credit pool (100× the free tier).
- **Dedicated HF Inference Endpoint:** $50–100/month (your own warm model instance, unlimited calls within the contract).
- **Self-hosted inference:** vLLM, TensorRT-LLM, or huggingface/transformers on a GPU instance ($30–100/month depending on model size and desired throughput).

---

### Supabase free tier pause (7 idle days, manual resume)

**What breaks:** Free Supabase projects pause after ~7 days of low activity. The database is accessible but frozen — queries time out or fail. Resume is a **manual dashboard action** (incoming requests do not auto-wake it, unlike Spaces).

**Impact:**
- `/api/v1/embed` stores vectors in Supabase. After the project pauses, embed requests hang or fail with a database error (502 or 504).
- `/api/v1/search` queries the paused database → same hang.
- **Silent failure mode:** if you don't check the demo for a week, it's broken. Customers clicking a link days later see a broken `/search` endpoint.

**Mitigation:** Keep-alive workflow (`.github/workflows/keepalive.yml`) pings `/api/v1/search` daily, which queries Supabase and keeps it active.

**Long-term failure mode:** if paused >90 days, the project becomes restorable via backup download only. Not a concern if the keep-alive runs daily.

**Production upgrade:**
- **Supabase Pro:** $25/month, no pause, 100 GB storage, 10,000 concurrent connections.
- **Self-hosted Postgres + pgvector:** Docker + managed Postgres (AWS RDS, GCP Cloud SQL, DigitalOcean, Render): $15–50/month depending on storage and throughput.

---

### Synchronous request model (no queue)

**What breaks:** Every endpoint blocks on inference. Classify (zero-shot NLI) takes 2–5 seconds; sentiment takes 100–500 ms (API) or 100–200 ms (local fallback); embed takes 200–500 ms for 20 documents. If 10 requests arrive simultaneously, the 10th waits for the previous 9 to complete.

**Sustainable load:** ~10 requests/sec for sentiment (API or fallback), ~2 requests/sec for classify, ~5 requests/sec for embed (assuming 10 docs per request).

**Breaking point:** Consistent >10 concurrent requests to classify or >30 concurrent requests to sentiment will queue requests and surface >30 s response times.

**Production upgrade:**
- **Async job queue** (Celery, Inngest, Bull on Redis): Enqueue inference jobs, return immediately to the client, deliver results via webhook or polling.
- Requires a separate worker tier and a message broker ($0–50/month depending on traffic volume).

---

### No API authentication or rate limiting (public endpoints)

**What breaks:** Any client can call your endpoints without credentials. No per-client rate limits — only request-size caps (text ≤2000 chars, labels 2–10, k ≤20).

**Risk:** Malicious actor discovers your Space URL and floods it with requests, exhausting the free quota or overloading the compute.

**Sustainable posture:** Treat this as a portfolio demo, not a customer-facing service. Share the Space URL in proposals, videos, and job applications — expect 10–100 requests/week per link, not 10,000 requests/day.

**Production upgrade:**
- **API key authentication** (fastapi-users, auth0): Issue keys, track per-key rate limits (e.g., 100 requests/minute per key).
- **Rate limiting middleware** (slowapi, gatekeeper): Global + per-IP/per-key rate limits.
- Documented as v1.1 scope; not built in v1.

---

## Combined free-tier budget

On the $0-per-month infrastructure:

| Component | Limit | Metric |
|-----------|-------|--------|
| Compute | 2 vCPU, 16 GB RAM | Sustains ~10 concurrent requests (sentiment) or ~2 (classify). |
| Storage | 50 GB (Spaces) + 500 MB (Supabase free) | ~100,000 documents with 384-dim vectors (each ~1.5 KB). |
| Inference quota | $0.10/month | ~100 classify calls, unlimited sentiment (local fallback). |
| Supabase storage | ~1 GB pgvector | ~700,000 vectors at 384 dimensions. |
| Supabase pause | Every 7 days idle | Manual resume; keep-alive mitigates. |
| Space sleep | Every 48 h idle | ~1 min cold start; keep-alive mitigates. |

**Practical single-author demo:** 3–5 walkthrough demos per week (sentiment + classify + embed + search) + a GitHub Actions keep-alive ping = sustainable on free tier for 6+ months.

---

## Production upgrade path

### Phase: move off free tier (Months 1–3 if shipping with this code)

**Priority 1 (must have for customer-facing):**
- Migrate Supabase from free to Pro ($25/month): no pause, 100 GB storage, dedicated support.
- Move HF Spaces to dedicated Inference Endpoint ($50–100/month) or always-on Space ($10/month).
- Implement API keys and per-key rate limiting (v1.1 scope, 40 hours).

**Cost:** $85–150/month.

### Phase: scale inference (if request volume exceeds 10 req/sec)

**Add async job queue:**
- Enqueue sentiment/classify/embed requests → return job ID immediately.
- Worker pool (2–4 workers) dequeues and runs inference asynchronously.
- Client polls `/api/v1/jobs/{job_id}` for results or receives webhook callback.
- Message broker: Redis (self-hosted on Railway $7/month, or managed on AWS ElastiCache $15+/month).

**Cost:** +$20–40/month for Redis + 40 hours development.

### Phase: scale embeddings and search (if corpus exceeds 1M documents)

**Optimize pgvector:**
- Index tuning: HNSW parameter tuning (`m`, `ef_construction`) for your query patterns.
- Sharding: if corpus exceeds 10M documents, partition by document ID or semantic cluster.
- Alternative: migrate to specialized vector DB (Weaviate, Pinecone, Milvus) for sub-second search at scale.

**Cost:** +0–100/month depending on storage tier choice.

### Phase: reduce model inference latency (if cold-start or classify latency dominates)

**Replace HF Inference API with dedicated endpoint:**
- Spin up a vLLM or TensorRT-LLM server on a GPU instance (A100 or cheaper T4).
- Reduced latency: classify 500 ms (API) → 100 ms (dedicated).
- Cost: $100–500/month for GPU compute (depends on model and batch size).

**Alternatively, use quantized models:**
- Quantize bart-large-mnli to INT8 or ONNX; run locally or on cheaper inference infra.
- Trade-off: 2–3% accuracy loss, 2× throughput gain.

---

## Notes on specific features

### Render free (512 MB) cannot host the full stack

The local sentiment fallback is ~1.04 GiB (model weights) loaded into memory at inference time. Render free tier provides 512 MB total RAM. A degraded embeddings-only service is theoretically possible (sentence-transformers alone: ~200–300 MB), but:
1. Sentiment fallback is a core demo differentiator: "here's why you need a fallback when the API fails."
2. Removing it reduces the portfolio's claim surface.

**Verdict:** Deploy on Hugging Face Spaces (16 GB, free Docker tier is sufficient). If forced onto Render, disable the local sentiment fallback and handle 402/429/503 with honest HTTP 503 responses (document the degradation).

### Why pgvector over a managed vector DB?

- **Pinecone ($0–100/month depending on index size):** managed, sub-millisecond search latency, no operational overhead. Downside: vendor lock-in, extra API call latency.
- **Weaviate ($0 self-hosted, $200+/month cloud):** open-source, mature, native vector + full-text hybrid search.
- **pgvector on Supabase:** already running PostgreSQL for other data; pgvector is a free extension; cosine search in 1–50 ms on 100K documents.

**Verdict:** pgvector is the right choice for a portfolio artifact (low cost, no vendor lock-in, demonstrates Postgres expertise). Scale concerns are documented; upgrade path is clear.
