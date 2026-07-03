# Bounded retry

Max **2 attempts** total per remote call (initial + one retry). Retry applies **only** to the transient 5xx class — quota (402), rate limit (429), and timeout never retry (see rules/error-handling.md). Retry delay: **250 ms**, capped at 1 s. Hardcoded in `backend/utils/retry.py` — never configurable upward, not via env var, not via parameter default (SPEC.md D4, wording per SPEC-AMENDMENTS.md A3).

**Why:** unbounded or configurable retries against a metered free tier are how you burn the credit pool and hang demos. The cap is the same discipline as ReelMind's `retryCount < 2`.

**How to apply:** any loop or recursion touching httpx must show its bound in the same function. If a review finds a retry path without a visible hardcoded cap, that is a blocking defect. `tests/test_retry.py` asserts the cap, the delay, and the per-class routing (only the transient class retries).
