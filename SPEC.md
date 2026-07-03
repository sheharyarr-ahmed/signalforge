# SPEC.md — SignalForge

Production-grade NLP inference service on Hugging Face open-source models. Portfolio artifact for SheryLabs. Zero-cost across every tier. Single author: Sheharyar Ahmed.

---

## Goal

Ship a public, deployed FastAPI service that demonstrates three Hugging Face NLP deployments without any GPU or paid compute, proving open-source ML deployment capability for Upwork bidding.

The three capabilities, each exposed as a versioned API endpoint:

1. **Multi-language sentiment analysis** (`POST /api/v1/sentiment`). Text in any language goes to the Hugging Face Inference API (free tier). If the API returns a rate-limit (429), a cold-start (503), or times out, the request falls back to a locally cached model running on CPU. Every response reports which path served it.

2. **Zero-shot document classification** (`POST /api/v1/classify`). Document text plus a caller-supplied label set (e.g. legal, financial, marketing, technical) goes to a zero-shot NLI model. No training data, no fine-tuning. Returns the winning label plus the full score distribution.

3. **Local embeddings + semantic search** (`POST /api/v1/embed`, `POST /api/v1/search`). Embeddings generated locally via sentence-transformers (all-MiniLM-L6-v2, 384 dimensions, CPU). Stored and queried in Supabase pgvector via cosine similarity. Zero OpenAI dependency — this is the "no embedding-API lock-in" proof.

Every response from every endpoint carries an `inference_metadata` object: `model`, `provider` ("huggingface_api" or "local"), `processing_time_ms`, `fallback_triggered`, `confidence`. This is the traceability discipline (the SignalForge equivalent of AuditDoc's mandatory citations).

**Business outcome:** after shipping, SignalForge unlocks bids on Hugging Face developer jobs, NLP engineer jobs, multi-language NLP jobs, document-classification automation jobs, and cost-conscious "we don't want OpenAI lock-in" clients. It becomes the seventh public portfolio anchor alongside ReelMind, AuditDoc, and FocusFrame.

**Deliverables:** public GitHub repo (github.com/sheharyarr-ahmed/signalforge), live deployment URL, README with Mermaid architecture diagram, docs/SCALING.md with honest free-tier limitation disclosure, 60-second demo recording of all three endpoints.

**Budget:** $0 cash. 6–10 hours build time. The Anthropic API is NOT used in this project's runtime — Hugging Face is the AI provider and its Inference API free tier plus local CPU models cover everything. Claude Code is the build tool only.

---

## Files

```
signalforge/
├── README.md                      # Portfolio hook, Mermaid diagram, endpoint docs, run instructions
├── SPEC.md                        # This file
├── .gitignore                     # Python standard + .env* + model cache dirs
├── .env.template                  # HF_API_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY, ENVIRONMENT, LOG_LEVEL
├── requirements.txt               # Exact-pinned versions
├── Dockerfile                     # python:3.11-slim, CPU-only, for HF Spaces / Render
├── .githooks/
│   └── commit-msg                 # Mechanically rejects AI-attribution strings
│
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory, CORS, exception handlers, router mounting
│   ├── config.py                  # Pydantic Settings from env vars
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py              # InferenceMetadata, ErrorResponse
│   │   ├── requests.py            # SentimentRequest, ClassifyRequest, EmbedRequest, SearchRequest
│   │   └── responses.py           # SentimentResponse, ClassifyResponse, EmbedResponse, SearchResponse
│   ├── services/
│   │   ├── __init__.py
│   │   ├── hf_client.py           # Async httpx client: 3-class error handling + bounded retry + backoff
│   │   ├── sentiment.py           # API-first with local fallback orchestration
│   │   ├── classifier.py          # Zero-shot via HF API (bart-large-mnli)
│   │   └── embedder.py            # sentence-transformers local wrapper, lazy singleton load
│   ├── db/
│   │   ├── __init__.py
│   │   ├── supabase_client.py     # Connection + pgvector insert/query
│   │   └── migrations.sql         # CREATE EXTENSION vector; documents table with vector(384) column + cosine index
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py              # GET /health
│   │   ├── sentiment.py           # POST /api/v1/sentiment
│   │   ├── classify.py            # POST /api/v1/classify
│   │   └── embeddings.py          # POST /api/v1/embed, POST /api/v1/search
│   └── utils/
│       ├── __init__.py
│       ├── logging.py             # structlog JSON config
│       ├── retry.py               # exponential backoff (250ms → 1s), max 2 attempts, per-error-class routing
│       └── errors.py              # HFRateLimitError, HFColdStartError, HFTimeoutError, VectorStoreError
│
├── tests/
│   ├── conftest.py                # fixtures, mocked httpx transport
│   ├── test_health.py
│   ├── test_sentiment.py          # happy path, 429→fallback, 503→retry, malformed input
│   ├── test_classify.py           # happy path, custom labels, label-count bounds
│   ├── test_embeddings.py         # embed shape (384-dim), search top-k, empty-store behavior
│   └── test_retry.py              # backoff timing, retry cap, error-class routing
│
├── docs/
│   ├── ARCHITECTURE.md            # decision rationale, request-flow diagram
│   ├── SCALING.md                 # honest free-tier limits + production upgrade path
│   └── DEPLOYMENT.md              # step-by-step deploy guide incl. all manual UI steps
│
└── .claude/
    ├── CLAUDE.md                  # project bible: Karpathy preamble, anti-pattern checklist, attribution rules
    ├── settings.json              # Stop-hook wiring to verify.sh
    ├── verify.sh                  # pytest -q (the gate the Stop hook runs)
    ├── agents/
    │   ├── api-architect.md       # routes + Pydantic contracts (sonnet)
    │   ├── hf-integrator.md       # HF client, fallback tree, retry (sonnet)
    │   ├── vector-engineer.md     # sentence-transformers + pgvector (sonnet)
    │   └── docs-deploy.md         # README, Mermaid, deploy guide (haiku)
    ├── skills/
    │   ├── fastapi-routes.md
    │   ├── pydantic-schemas.md
    │   ├── hf-inference-client.md
    │   ├── sentence-transformers.md
    │   ├── pgvector-schema.md
    │   └── structured-logging.md
    └── rules/
        ├── no-fabrication.md
        ├── error-handling.md
        ├── bounded-retry.md
        ├── inference-metadata.md
        └── no-claude-attribution.md
```

---

## Decisions

**D1 — Hugging Face Spaces (Docker) is the primary deployment target, Render free tier is the fallback.**
Alternative considered: Render free (512 MB RAM, sleeps at 15 min). Rejected as primary because sentence-transformers loaded in memory sits at 200–300 MB, leaving almost no headroom on 512 MB. HF Spaces free tier gives 2 vCPU and 16 GB RAM on a Docker Space at $0, and deploying an HF portfolio project ON Hugging Face infrastructure is itself a positioning signal to HF-ecosystem clients. Trade-off: Spaces sleep after ~48 h of inactivity (vs 15 min on Render) — strictly better. The Dockerfile is written host-agnostic so either target works.

**D2 — Hugging Face Inference API for hosted models, local CPU models for fallback and embeddings.**
Alternative considered: everything local. Rejected because demonstrating the hosted Inference API (auth, error semantics, model routing) is exactly the skill HF clients hire for. Alternative considered: OpenAI. Rejected — defeats the entire "no lock-in" positioning.

**D3 — Three-class HF error handling, not a generic try/except.**
503 with `estimated_time` header = model cold-starting → wait and retry once. 429 = quota exhausted → immediate local fallback, no retry. Timeout (>10 s) = immediate local fallback. Each class routes differently in `utils/retry.py`. A single catch-all would either hammer a loading model or give up on a recoverable one.

**D4 — Bounded retry: max 2 attempts, exponential backoff 250 ms → 1 s.**
Same retry-cap discipline as ReelMind's `retryCount < 2`, extended with backoff because these are remote calls, not in-process state-machine loops. Hardcoded cap, never configurable upward.

**D5 — Models locked.**
Sentiment: `cardiffnlp/twitter-xlm-roberta-base-sentiment` (multilingual, ~80 MB, CPU-viable — also the local fallback). Zero-shot: `facebook/bart-large-mnli` (API-only; 1.6 GB makes it API-only by design, and that asymmetry is documented as a deliberate decision). Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local-only, the industry-standard free embedding).

**D6 — pgvector column locked at vector(384) with a cosine-distance index, migrated in Phase 1, not Phase 3.**
Dimensionality is a one-way door: changing it later means re-embedding everything. Locked to MiniLM's 384 now. Index: `ivfflat` with `vector_cosine_ops` (HNSW unnecessary at portfolio scale).

**D7 — `inference_metadata` on every response, named that and not "citations."**
AuditDoc's "citations" means page-level source attribution; reusing the word here would muddy the portfolio vocabulary. Same discipline (traceable, verifiable outputs), correct name for what it is: model version, provider path, latency, fallback flag, confidence.

**D8 — Pydantic v2 strict mode at every boundary.**
Request validation, response serialization, and Settings from env. No `Any`, no implicit coercion. Field constraints (text length caps, label-count bounds 2–10, k bounds 1–20) live in the schema, not in handler code.

**D9 — structlog JSON logging from commit one.**
Every request logs endpoint, duration, provider path, fallback flag, model. This is the observability story told in proposals; bolting it on later produces inconsistent fields.

**D10 — Zero Claude attribution, mechanically enforced.**
Git author locked to Sheharyar Ahmed / sheharyar.softwareengineer@gmail.com. `.githooks/commit-msg` (activated via `git config core.hooksPath .githooks`) rejects any commit containing "Claude", "Co-Authored-By", "Generated with", "Anthropic", or the robot emoji. Contributor graph shows one author. This inherits the global `~/.claude/CLAUDE.md` rule and adds the per-repo mechanical guard.

**D11 — Conventional commits, one commit per completed unit.**
`chore(phase-0a):`, `feat(sentiment):`, `test(retry):`, `docs(scaling):`. Imperative mood. No commit lands unless `verify.sh` (pytest) is green — enforced by the Stop hook.

**D12 — Manual UI steps are Claude Code's responsibility to REQUEST, never assume.**
The build has five unavoidable human-in-browser moments. At each, Claude Code must stop, print exact instructions, and wait for confirmation:
  1. Hugging Face account + free API token creation (huggingface.co → Settings → Access Tokens → Read token)
  2. Supabase project creation + enabling the `vector` extension (Dashboard → Database → Extensions → vector)
  3. Copying Supabase URL + service key and HF token into `.env` locally
  4. Creating the HF Space (huggingface.co → New Space → Docker SDK → CPU basic free) and adding the same secrets in Space settings
  5. GitHub repo metadata after deploy: About description, topics (`fastapi`, `huggingface`, `nlp`, `sentence-transformers`, `pgvector`, `zero-shot-classification`, `semantic-search`), website field pointing at the live Space URL, social preview image

**D13 — Anthropic API deliberately absent from runtime.**
This project's differentiator is open-source-model deployment. Claude Code builds it; Claude does not run inside it. If a future v1.1 adds an LLM feature, that is a separate spec.

**D14 — Anti-fabrication walls (locked claims).**
After shipping, the defensible claims are: production NLP pipeline on HF open-source models, multi-language sentiment with API/local fallback, zero-shot classification with custom label sets, local embeddings via sentence-transformers, vector search on Supabase pgvector, cost-optimization patterns. Forbidden claims: custom model training, fine-tuning, custom embeddings, GPU-optimized inference, production traffic at scale.

---

## Out of scope

- **Any LLM integration** (Claude, GPT, open-source chat models). This is an NLP inference service, not an agent.
- **Model training or fine-tuning** of any kind. Pre-trained checkpoints only.
- **GPU inference** anywhere, including free GPU quotas — the CPU-only story is the point.
- **Authentication / API keys on the endpoints.** Public demo endpoints with input-size caps are the correct scope; auth is a documented v1.1 item in SCALING.md.
- **Rate limiting middleware** on our own API (documented as production upgrade, not built).
- **Frontend / UI.** FastAPI's auto-generated `/docs` (Swagger) IS the demo surface, and the 60-second recording uses it. No Next.js app.
- **Batch/async job queues** (Celery, Inngest-equivalents). Requests are synchronous; documented honestly.
- **Multi-model routing or model registries.** Three locked models, no dynamic selection.
- **Caching layers** (Redis) beyond the in-process lazy model singleton.
- **CI/CD pipelines.** No GitHub Actions in v1 (zero-spend rule on Actions minutes is not the issue — scope discipline is). Local verify.sh is the gate.
- **Monetization layer** (Whop, Stripe). Portfolio artifact, not a product.
- **Kubernetes, Terraform, or any infra-as-code.** One Dockerfile, one host.

---

## Verification

**Per-phase gates (verify.sh runs `pytest -q`; the Stop hook blocks any turn ending with a dirty tree and failing tests):**

- Phase 0a: scaffold files exist, `.githooks/commit-msg` rejects a test commit containing "Co-Authored-By: Claude", accepts a clean one.
- Phase 1: `uvicorn backend.main:app` boots; `GET /health` returns 200 with `{"status": "ok"}`; pytest green on health + retry tests; pgvector migration applied on Supabase (manual confirmation step).
- Phase 2: `POST /api/v1/sentiment` returns a valid `SentimentResponse` against the live HF API; forcing a mocked 429 in tests triggers local fallback with `fallback_triggered: true`; forcing a mocked 503 triggers exactly one retry.
- Phase 3: `POST /api/v1/classify` returns the correct winning label on a known test document; `POST /api/v1/embed` returns 384-dim vectors; `POST /api/v1/search` returns top-k results ordered by descending similarity on a seeded 10-document corpus.
- Phase 4: live Space URL responds on all endpoints from a cold browser; README renders the Mermaid diagram on GitHub; SCALING.md contains the honest limitation disclosure.

**End-to-end check (the single command-level proof the system works):**

```bash
BASE=https://<space-url>   # or http://localhost:8000

curl -s $BASE/health | jq .status                          # "ok"

curl -s -X POST $BASE/api/v1/sentiment \
  -H 'Content-Type: application/json' \
  -d '{"text": "Este producto es increíble, lo recomiendo totalmente"}' \
  | jq '.label, .inference_metadata.provider'               # "positive", provider reported

curl -s -X POST $BASE/api/v1/classify \
  -H 'Content-Type: application/json' \
  -d '{"text": "The party of the first part agrees to indemnify...", "labels": ["legal","financial","marketing","technical"]}' \
  | jq .predicted_label                                     # "legal"

curl -s -X POST $BASE/api/v1/embed \
  -H 'Content-Type: application/json' \
  -d '{"documents": ["Invoices are due within 30 days", "The rocket launched successfully", "Quarterly revenue grew 12 percent"]}' \
  | jq '.inference_metadata.model'                          # all-MiniLM-L6-v2

curl -s -X POST $BASE/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "payment terms", "k": 2}' \
  | jq '.results[0].document'                               # the invoices document ranks first
```

All five commands succeeding against the deployed URL, plus `pytest -q` fully green locally, plus `git log --format="%an %B" | grep -iE "claude|anthropic|co-authored"` returning nothing, is the definition of done.

**Human verification (anti-fabrication requirement):** before the repo goes into any proposal, Sheharyar can explain from memory: the three error classes and why each routes differently, why bart-large-mnli is API-only while the sentiment model is dual-path, why the vector column is 384 and what changing it would cost, and what breaks first under real load. `/defend` session against this repo before first bid referencing it.

---

**END OF SPEC**
