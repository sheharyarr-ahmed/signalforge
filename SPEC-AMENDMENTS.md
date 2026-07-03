# SPEC-AMENDMENTS.md — SignalForge

Output of the spec-review run (2026-07-04): 4 web-recon agents verified the platform reality against live sources; 4 review lenses produced findings; every blocker/major finding survived a 3-voter adversarial verification panel (17 survived, 7 were refuted and dropped). Where an amendment conflicts with SPEC.md, **the amendment wins** — each one is grounded in a live-verified fact, not preference. Merge these into SPEC.md when convenient; A7's keep-alive question is the only open decision.

---

## Blockers (build fails or ships broken without these)

### A1 — D2: the spec's API host is dead
`api-inference.huggingface.co` no longer resolves in DNS. The successor is Inference Providers:
`POST https://router.huggingface.co/hf-inference/models/{model_id}`, header `Authorization: Bearer $HF_API_TOKEN`.
Both locked models are live and warm on the `hf-inference` provider (their only provider). Sentiment payload `{"inputs": "<text>"}`; zero-shot payload `{"inputs": "<text>", "parameters": {"candidate_labels": [...]}}`; both return `{label, score}` arrays.
**D2 rewrite:** "Hugging Face Inference Providers (provider: hf-inference, successor of the legacy Inference API) for hosted models, local CPU models for fallback and embeddings."

### A2 — D3: error taxonomy is obsolete — four classes, not three
The free tier is now a **$0.10/month credit pool**; exhaustion returns **HTTP 402** (unhandled by the spec's D3 → public demo dies with a raw 500 mid-month). 429 still exists but means a 5-minute-window rate limit. The `503 + estimated_time` cold-start contract is defunct (hf-inference serves warm models; the official client removed all wait-for-model handling).
**D3 rewrite:** 402 quota → `HFQuotaError` → local fallback, cache exhausted state in-process until month rollover; 429 rate limit → `HFRateLimitError` → local fallback, no retry; 503/5xx transient → `HFTransientError` → retry exactly once; >10 s timeout → `HFTimeoutError` → local fallback. For `/classify` (no local model, D5): every class terminates in an honest 503 `ErrorResponse`; `fallback_triggered` never true. Tests mock 402, 429, 503, and timeout separately.

### A3 — D4: the two-step backoff schedule is unreachable
Max-2-attempts means exactly one backoff interval — "exponential 250 ms → 1 s" can never execute its second step, and only the transient class retries at all.
**D4 rewrite:** "Bounded retry: max 2 total attempts (initial + one retry, transient 5xx class only). Retry delay 250 ms, capped at 1 s. Hardcoded, never configurable upward." Drop the word "exponential".

### A4 — D5/D1: the sentiment model is ~1.04 GiB, not ~80 MB — Render fallback is impossible
`cardiffnlp/twitter-xlm-roberta-base-sentiment` weights: 1,112,271,561 bytes (HEAD-verified), ~1.1–1.5 GB RAM loaded fp32. Fine on Spaces (16 GB); **impossible on Render free (512 MB / 0.1 CPU)**.
**D5 correction:** "(multilingual, ~1.04 GiB on disk / ~1.1–1.5 GB loaded, CPU-viable within Spaces' 16 GB — also the local fallback, lazy-loaded singleton)".
**D1 correction:** HF Spaces is mandatory, not preferred. Honest fallback statement: "Render free cannot host the full stack; the only degraded mode there would be embeddings-only without local sentiment fallback — documented in SCALING.md, not built." Add the corrected numbers to D14's defensible claims (this figure is exactly what gets probed in interviews).

### A5 — D6: ivfflat on an empty table is degenerate — use HNSW
The Phase-1 migration runs before any rows exist; ivfflat trains centroids from existing data, so the index would be built untrained. Supabase's current official guidance: HNSW by default.
**D6 rewrite:** `create index on documents using hnsw (embedding vector_cosine_ops);` — interview rationale: "ivfflat needs trained centroids from pre-existing rows; HNSW builds incrementally on an empty table." Additionally, migrations.sql **must** define `match_documents(query_embedding vector(384), match_count int)` — PostgREST exposes no pgvector operators, so supabase-py `.rpc()` against that function is the only supported query path (see A6: direct Postgres is blocked from Spaces anyway). Pin `supabase==2.31.0` (breaking 3.0 alpha on PyPI).

### A6 — Files/Dockerfile: the specced Dockerfile cannot produce a running Space
Spaces contract (all live-verified): container runs as UID 1000 non-root (a root-oriented image crashes with cache permission errors on first model load); app must listen on 0.0.0.0:7860 (or declare `app_port`); the Space README needs YAML front-matter (`sdk: docker`, `app_port: 7860`); disk is **ephemeral** — models must be downloaded at image build time into a user-writable `HF_HOME`; outbound traffic is restricted to ports 80/443/8080, so **Supabase must be reached via HTTPS/PostgREST only, never direct Postgres**, and migrations are applied from the SQL editor, not the app. Torch must install from `--index-url https://download.pytorch.org/whl/cpu` or the image pulls multi-GB CUDA wheels.
*Implemented in the committed `Dockerfile` and `requirements.txt` (exact pins verified: fastapi 0.139.0, uvicorn 0.49.0, pydantic 2.13.4, pydantic-settings 2.14.2, httpx 0.28.1 — capped by supabase — structlog 26.1.0, sentence-transformers 5.6.0, torch 2.12.1, transformers 5.13.0, supabase 2.31.0, pytest 9.1.1, pytest-asyncio 1.4.0, pytest-httpx 0.36.2). Local Python 3.14.4 is fully supported by this stack; a 3.11 venv is optional Docker parity, not a requirement.*

### A7 — Verification/D12: Supabase free projects pause after ~7 idle days — the demo dies silently
Free projects pause after ~7 days of low activity; resume is a **manual dashboard action** (incoming requests never wake it, unlike Spaces); paused >90 days → restorable only via backup download. Every phase gate runs at deploy time, so the definition of done stays green while `/embed` and `/search` break for any client clicking weeks later.
**Amendments:**
- Add D12 step 6 (demo-day runbook, also in DEPLOYMENT.md): before any demo/recording/proposal link-out — (a) resume the Supabase project if paused, (b) ping the Space URL and allow ~1 min cold wake, (c) run the five-curl block.
- Reword Phase 4 gate: "after resuming Supabase and waking the Space, the live URL responds on all endpoints."
- Add Phase 5 durability gate: at T+7 days (or simulated pause), run the five-curl block cold; pass = all five succeed unaided OR the runbook restores full function in <5 minutes — must pass once before the first proposal referencing the repo.
- **OPEN DECISION:** the only zero-effort mitigation is a daily scheduled GitHub Actions ping to `/health` + `/api/v1/search` (keeps both Space and Supabase active, $0). This contradicts the locked "no CI/CD" out-of-scope item. Options: (a) carve out the exception as "keep-alive, not a pipeline" — recommended; (b) stay manual-runbook-only and accept that the demo needs a pre-bid resume ritual.

---

## Majors (spec is internally inconsistent or underspecified)

### A8 — D3: classify's failure contract was undefined
Covered by A2: `/classify` terminates every error class in an honest 503 `ErrorResponse` (e.g. "hosted-inference demo credits exhausted; resets monthly"); `fallback_triggered` never true for classify.

### A9 — D8: input caps were mandated but never quantified
The no-auth public posture leans on caps that had no values. Locked values (now in `.claude/skills/pydantic-schemas/SKILL.md`): sentiment/classify text ≤ 2000 chars; embed ≤ 20 documents × ≤ 2000 chars; search query ≤ 500 chars; labels 2–10; k 1–20.

### A10 — D7/Goal: `confidence` undefined for embed/search; model-name format ambiguous
`confidence: float | null` — top-label score for sentiment/classify, `null` for embed/search. `model` always carries the full HF repo id (`sentence-transformers/all-MiniLM-L6-v2`); update the E2E check's expected jq comment accordingly.

### A11 — .claude architecture: skills must be directories
Flat `.claude/skills/*.md` files are not discovered by current Claude Code — each skill must be `.claude/skills/<name>/SKILL.md` with name+description frontmatter. *Already implemented this way in this repo.* (Verified fine as specced: `.claude/rules/*.md` auto-loading, `model: sonnet|haiku` agent frontmatter, settings.json keys, Stop-hook syntax.)

---

## Minors (adopt during the relevant phase)

- **Phase 2 gate** mixes a live-API assertion into a mocked test suite — reword: live HF smoke check is a manual curl step; pytest covers mocked paths only.
- **D11 vs Verification**: the Stop hook gates turn-ends, not commits — commit-time greenness is procedural discipline, or add a pre-commit hook later.
- **SCALING.md** must enumerate mandatory disclosure bullets: Supabase 7-day pause + manual resume + 90-day limit; HF $0.10/month credits + 402 + classify's no-fallback behavior; Space 48 h sleep + ~1 min cold wake.
- **Supabase free plan allows only 2 active projects** — D12 step 2 precondition: verify a slot is free before creating the project; never silently sacrifice another live demo.
- **requirements.txt/Dockerfile pins** — implemented, see A6.

## Verified-unchanged (no action)

HF Spaces CPU Basic free tier: 2 vCPU / 16 GB RAM / 50 GB disk, 48 h sleep with auto-wake on visit, stable `https://<user>-<space>.hf.space` URL — D1's platform choice is confirmed (and now mandatory per A4). Space secrets inject as env vars, so the Pydantic Settings design works unchanged. all-MiniLM-L6-v2 remains the standard 384-dim free embedding — the `vector(384)` lock stands. Supabase HTTPS path consumes zero Postgres connections. Both locked models remain available and warm on hf-inference.
