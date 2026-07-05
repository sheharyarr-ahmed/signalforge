"""Raw async httpx client for Hugging Face Inference Providers (SPEC-AMENDMENTS.md A1).

The legacy `api-inference.huggingface.co` host is dead (DNS removed) — every call
goes through the router. Raw httpx (not `AsyncInferenceClient`) is used deliberately:
the four-class error routing in rules/error-handling.md needs direct status-code
access, which the official client hides behind its own retry/normalization layer.
"""

import httpx

from backend.config import get_settings
from backend.utils.errors import (
    HFError,
    HFQuotaError,
    HFRateLimitError,
    HFTimeoutError,
    HFTransientError,
)

HF_ROUTER = "https://router.huggingface.co/hf-inference/models/{model_id}"

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Lazy module-level singleton — never build a client per request."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def call_model(model_id: str, payload: dict) -> list:
    """POST to the HF router for `model_id`, raising a typed error per class.

    Success returns the parsed JSON body, with the text-classification
    double-nesting (`[[{...}]]`) collapsed to `[{...}]`. Zero-shot's dict
    response form (`{"labels": [...], "scores": [...]}`) is passed through
    unchanged — callers that need it handle that shape themselves.
    """
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.hf_api_token}",
        "Content-Type": "application/json",
    }

    try:
        resp = await get_client().post(
            HF_ROUTER.format(model_id=model_id), json=payload, headers=headers
        )
    except httpx.TimeoutException as exc:
        raise HFTimeoutError(f"HF request timed out for {model_id}") from exc

    if resp.status_code == 402:
        raise HFQuotaError(f"HF quota exhausted for {model_id}", status_code=402)
    if resp.status_code == 429:
        raise HFRateLimitError(f"HF rate limited for {model_id}", status_code=429)
    if resp.status_code >= 500:
        raise HFTransientError(
            f"HF transient error {resp.status_code} for {model_id}",
            status_code=resp.status_code,
        )
    if resp.status_code >= 400:
        raise HFError(
            f"unexpected HF status {resp.status_code}", status_code=resp.status_code
        )

    data = resp.json()
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
        data = data[0]
    return data
