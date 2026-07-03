# Four-class HF error handling

Hugging Face API failures are handled by class, never by a generic catch-all. This amends SPEC.md D3 per `SPEC-AMENDMENTS.md` A2 — the 2026 Inference Providers error contract differs from the spec's original assumptions (verified live 2026-07):

| Class | Signal | Route |
|---|---|---|
| Quota exhausted | 402 (free tier = $0.10/month credits) | immediate local fallback; cache exhausted state in-process until month rollover — never re-hit the router per request |
| Rate limit | 429 (5-minute window, `RateLimit` headers) | immediate local fallback, no retry |
| Transient server error | 503/5xx (no `estimated_time` — that contract is defunct) | retry exactly once with backoff |
| Timeout | > 10 s | immediate local fallback, no retry |

Each class is a typed exception in `backend/utils/errors.py` (`HFQuotaError`, `HFRateLimitError`, `HFTransientError`, `HFTimeoutError`) and routes through `backend/utils/retry.py`.

"Local fallback" applies to **sentiment only**. `/api/v1/classify` has no local model (bart-large-mnli is API-only by design): every class terminates in an honest HTTP 503 `ErrorResponse`; `fallback_triggered` is never true for classify.

**Why:** a catch-all either hammers a failing endpoint or gives up on a recoverable call — and an unhandled 402 is the near-certain failure mode of a public $0-budget demo. The four-class tree is also the portfolio talking point; it must exist in the code exactly as described.

**How to apply:** `hf_client.py` raises typed errors only; no bare `except`, no `except Exception` around HF calls. Every fallback sets `fallback_triggered: true`. Tests cover each class separately (mocked 402, 429, 503, forced timeout).
