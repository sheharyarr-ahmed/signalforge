"""Tests for the bounded-retry chokepoint (SPEC.md D4, SPEC-AMENDMENTS.md A3).

Asserts: retry cap (max 2 attempts total), the 250 ms delay, and per-class
routing (only HFTransientError retries; HFQuotaError, HFRateLimitError,
HFTimeoutError propagate immediately with no retry).
"""

import asyncio

import pytest

from backend.utils.errors import (
    HFQuotaError,
    HFRateLimitError,
    HFTimeoutError,
    HFTransientError,
)
from backend.utils.retry import MAX_ATTEMPTS, RETRY_DELAY_S, with_retry


@pytest.fixture
def recorded_sleeps(monkeypatch):
    """Monkeypatch asyncio.sleep to a no-op that records the delays passed."""
    delays: list[float] = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return delays


@pytest.mark.asyncio
async def test_transient_then_success_returns_sentinel(recorded_sleeps):
    sentinel = object()
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) == 1:
            raise HFTransientError("503 upstream")
        return sentinel

    result = await with_retry(fn)

    assert result is sentinel
    assert len(calls) == 2
    assert recorded_sleeps == [0.25]


@pytest.mark.asyncio
async def test_retry_cap_raises_after_max_attempts(recorded_sleeps):
    calls = []

    async def fn():
        calls.append(1)
        raise HFTransientError("503 upstream")

    with pytest.raises(HFTransientError):
        await with_retry(fn)

    assert len(calls) == MAX_ATTEMPTS == 2
    assert recorded_sleeps == [0.25]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_cls",
    [HFQuotaError, HFRateLimitError, HFTimeoutError],
)
async def test_non_transient_classes_never_retry(recorded_sleeps, error_cls):
    calls = []

    async def fn():
        calls.append(1)
        raise error_cls("no retry for this class")

    with pytest.raises(error_cls):
        await with_retry(fn)

    assert len(calls) == 1
    assert recorded_sleeps == []


@pytest.mark.asyncio
async def test_happy_path_no_retry_needed(recorded_sleeps):
    sentinel = object()
    calls = []

    async def fn():
        calls.append(1)
        return sentinel

    result = await with_retry(fn)

    assert result is sentinel
    assert len(calls) == 1
    assert recorded_sleeps == []


def test_retry_delay_constant_is_250ms():
    assert RETRY_DELAY_S == 0.25
