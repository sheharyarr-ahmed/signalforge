"""Single bounded-retry chokepoint for Hugging Face calls (SPEC.md D4, SPEC-AMENDMENTS.md A3).

Hardcoded. Never configurable via env var or parameter default — the cap is the same
discipline as ReelMind's `retryCount < 2`, applied to a metered free tier.
"""

import asyncio

from backend.utils.errors import HFTransientError

MAX_ATTEMPTS = 2  # total attempts = initial + one retry; hardcoded
RETRY_DELAY_S = 0.25  # 250 ms, capped at 1 s


async def with_retry(fn, *args, **kwargs):
    """Await fn(*args, **kwargs). Retry ONLY on HFTransientError, at most once,
    after a 250 ms delay. All other exceptions (incl. HFQuotaError, HFRateLimitError,
    HFTimeoutError) propagate immediately with NO retry.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return await fn(*args, **kwargs)
        except HFTransientError:
            if attempt >= MAX_ATTEMPTS:
                raise
            await asyncio.sleep(min(RETRY_DELAY_S, 1.0))
