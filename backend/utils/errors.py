"""Typed error taxonomy for Hugging Face inference calls (SPEC.md D3, SPEC-AMENDMENTS.md A2).

Four classes, routed independently in backend/utils/retry.py and the service layer —
never a generic try/except around an HF call:

    HFQuotaError      402 monthly credit pool exhausted -> local fallback,
                      cache exhausted state in-process until month rollover.
    HFRateLimitError  429 5-minute-window rate limit     -> local fallback, no retry.
    HFTransientError  503/5xx transient server error     -> retry exactly once.
    HFTimeoutError    request exceeded the 10s timeout   -> local fallback, no retry.

For /api/v1/classify (no local model, D5) every class terminates in an honest
503 ErrorResponse instead of a fallback; fallback_triggered is never true there.
"""


class HFError(Exception):
    """Base class for all Hugging Face inference errors."""

    def __init__(self, message: str | None = None, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class HFQuotaError(HFError):
    """HTTP 402 — monthly $0.10 credit pool exhausted. Routes to local fallback."""


class HFRateLimitError(HFError):
    """HTTP 429 — 5-minute-window rate limit. Routes to local fallback, no retry."""


class HFTransientError(HFError):
    """HTTP 503/5xx — transient server error. The ONLY retryable class (retry exactly once)."""


class HFTimeoutError(HFError):
    """Request exceeded the 10 s timeout. Routes to local fallback, no retry."""


class VectorStoreError(Exception):
    """Supabase/pgvector failure. Not an HFError — unrelated to HF inference routing."""
