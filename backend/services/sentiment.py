"""Multi-language sentiment analysis: HF Inference Providers first, local CPU fallback.

Dual-path model (SPEC.md D5, SPEC-AMENDMENTS.md A4):
`cardiffnlp/twitter-xlm-roberta-base-sentiment` is used both as the hosted API
model and — lazy-loaded, CPU, ~1.1-1.5 GB in memory — as the local fallback.

Error routing (rules/error-handling.md, SPEC-AMENDMENTS.md A2):
    402 HFQuotaError      -> local fallback; cache exhausted state until month rollover
    429 HFRateLimitError  -> local fallback, no retry
    503/5xx HFTransientError -> already retried once by with_retry(); local fallback
    timeout HFTimeoutError -> local fallback, no retry
"""

import asyncio
import time
from datetime import datetime, timezone
from functools import lru_cache

import structlog

from backend.schemas.common import InferenceMetadata
from backend.schemas.responses import LabelScore, SentimentResponse
from backend.services.hf_client import call_model
from backend.utils.errors import (
    HFQuotaError,
    HFRateLimitError,
    HFTimeoutError,
    HFTransientError,
)
from backend.utils.retry import with_retry

log = structlog.get_logger(__name__)

SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# In-process quota cache (SPEC-AMENDMENTS.md A2): once a 402 is seen, never
# re-hit the router until the current UTC month rolls over.
_quota_exhausted_until: datetime | None = None


def _end_of_month_utc(now: datetime) -> datetime:
    if now.month == 12:
        return now.replace(
            year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    return now.replace(
        month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
    )


def _quota_active() -> bool:
    return (
        _quota_exhausted_until is not None
        and datetime.now(timezone.utc) < _quota_exhausted_until
    )


def reset_quota_state() -> None:
    """Test-only hook: clear the in-process quota cache between test cases."""
    global _quota_exhausted_until
    _quota_exhausted_until = None


def _build_response(
    *,
    scores: list[LabelScore],
    label: str,
    confidence: float,
    provider: str,
    fallback_triggered: bool,
    start: float,
) -> SentimentResponse:
    duration_ms = int((time.perf_counter() - start) * 1000)
    metadata = InferenceMetadata(
        model=SENTIMENT_MODEL,
        provider=provider,
        processing_time_ms=duration_ms,
        fallback_triggered=fallback_triggered,
        confidence=confidence,
    )
    log.info(
        "inference_complete",
        endpoint="/api/v1/sentiment",
        model=SENTIMENT_MODEL,
        provider=provider,
        fallback_triggered=fallback_triggered,
        duration_ms=duration_ms,
    )
    return SentimentResponse(label=label, scores=scores, inference_metadata=metadata)


async def analyze_sentiment(text: str) -> SentimentResponse:
    global _quota_exhausted_until
    start = time.perf_counter()

    if not _quota_active():
        try:
            raw = await with_retry(call_model, SENTIMENT_MODEL, {"inputs": text})
            scores = [
                LabelScore(label=str(item["label"]).lower(), score=float(item["score"]))
                for item in raw
            ]
            top = max(scores, key=lambda s: s.score)
            return _build_response(
                scores=scores,
                label=top.label,
                confidence=top.score,
                provider="huggingface_api",
                fallback_triggered=False,
                start=start,
            )
        except HFQuotaError as exc:
            _quota_exhausted_until = _end_of_month_utc(datetime.now(timezone.utc))
            log.warning(
                "hf_error",
                error_class="HFQuotaError",
                model=SENTIMENT_MODEL,
                error=str(exc),
            )
        except (HFRateLimitError, HFTimeoutError) as exc:
            log.warning(
                "hf_error",
                error_class=type(exc).__name__,
                model=SENTIMENT_MODEL,
                error=str(exc),
            )
        except HFTransientError as exc:
            log.warning(
                "hf_error",
                error_class="HFTransientError",
                model=SENTIMENT_MODEL,
                error=str(exc),
            )

    scores = await asyncio.to_thread(_run_local_sentiment, text)
    top = max(scores, key=lambda s: s.score)
    return _build_response(
        scores=scores,
        label=top.label,
        confidence=top.score,
        provider="local",
        fallback_triggered=True,
        start=start,
    )


@lru_cache(maxsize=1)
def _load_local_sentiment_model():
    """Lazy singleton load of the CPU fallback model (~1.1-1.5 GB loaded)."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL)
    model.eval()
    return tokenizer, model


def _run_local_sentiment(text: str) -> list[LabelScore]:
    """CPU inference for the local fallback path. Module-level so tests can
    monkeypatch it directly and never trigger the real ~1 GB model load.
    """
    import torch

    tokenizer, model = _load_local_sentiment_model()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**inputs).logits[0]
    probs = torch.softmax(logits, dim=-1)
    id2label = model.config.id2label
    return [
        LabelScore(label=str(id2label[i]).lower(), score=float(probs[i]))
        for i in range(len(probs))
    ]
