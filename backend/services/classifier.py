"""Zero-shot document classification via HF Inference Providers (bart-large-mnli).

API-only by design (SPEC.md D5): bart-large-mnli has no local fallback (1.6 GB
makes CPU fallback impractical, and that asymmetry vs. sentiment is deliberate).
Every HF error class propagates untouched from here — backend/main.py's
exception handler turns any HFError into an honest 503 ErrorResponse.
`fallback_triggered` is never true for this endpoint (rules/error-handling.md).
"""

import time

import structlog

from backend.schemas.common import InferenceMetadata
from backend.schemas.responses import ClassifyResponse, LabelScore
from backend.services.hf_client import call_model
from backend.utils.retry import with_retry

log = structlog.get_logger(__name__)

CLASSIFY_MODEL = "facebook/bart-large-mnli"


def _normalize_scores(raw) -> list[LabelScore]:
    """Handle both the `[{label,score}]` array form and the zero-shot dict
    form `{"labels": [...], "scores": [...]}` returned by the router.
    """
    if isinstance(raw, dict) and "labels" in raw and "scores" in raw:
        return [
            LabelScore(label=str(label), score=float(score))
            for label, score in zip(raw["labels"], raw["scores"])
        ]
    return [
        LabelScore(label=str(item["label"]), score=float(item["score"])) for item in raw
    ]


async def classify_text(text: str, labels: list[str]) -> ClassifyResponse:
    start = time.perf_counter()

    # No try/except here by design: every HF error class (quota, rate-limit,
    # transient, timeout) propagates to the router-level exception handler,
    # which returns an honest 503 ErrorResponse. Classify has no fallback.
    raw = await with_retry(
        call_model,
        CLASSIFY_MODEL,
        {
            "inputs": text,
            "parameters": {"candidate_labels": labels, "multi_label": False},
        },
    )

    scores = _normalize_scores(raw)
    top = max(scores, key=lambda s: s.score)
    duration_ms = int((time.perf_counter() - start) * 1000)

    metadata = InferenceMetadata(
        model=CLASSIFY_MODEL,
        provider="huggingface_api",
        processing_time_ms=duration_ms,
        fallback_triggered=False,
        confidence=top.score,
    )
    log.info(
        "inference_complete",
        endpoint="/api/v1/classify",
        model=CLASSIFY_MODEL,
        provider="huggingface_api",
        fallback_triggered=False,
        duration_ms=duration_ms,
    )
    return ClassifyResponse(
        predicted_label=top.label, scores=scores, inference_metadata=metadata
    )
