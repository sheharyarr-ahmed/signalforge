"""Tests for POST /api/v1/sentiment: happy path, the four HF error classes,
and malformed-input validation (SPEC.md D3/D8, SPEC-AMENDMENTS.md A2/A9).
"""

import httpx
import pytest
from fastapi.testclient import TestClient


def test_happy_path_returns_huggingface_api_result(client: TestClient, httpx_mock):
    httpx_mock.add_response(
        json=[
            {"label": "positive", "score": 0.97},
            {"label": "neutral", "score": 0.02},
            {"label": "negative", "score": 0.01},
        ]
    )

    response = client.post(
        "/api/v1/sentiment", json={"text": "Este producto es increible"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "positive"
    assert body["inference_metadata"]["provider"] == "huggingface_api"
    assert body["inference_metadata"]["fallback_triggered"] is False
    assert body["inference_metadata"]["confidence"] == pytest.approx(0.97)
    assert body["inference_metadata"]["model"] == (
        "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    )


def test_rate_limit_triggers_local_fallback(
    client: TestClient, httpx_mock, mock_local_sentiment
):
    httpx_mock.add_response(status_code=429)

    response = client.post("/api/v1/sentiment", json={"text": "hello there"})

    assert response.status_code == 200
    body = response.json()
    assert body["inference_metadata"]["provider"] == "local"
    assert body["inference_metadata"]["fallback_triggered"] is True
    assert body["label"] == mock_local_sentiment[0].label


def test_quota_exhausted_triggers_fallback_and_caches_state(
    client: TestClient, httpx_mock, mock_local_sentiment
):
    # Only ONE 402 response registered: the second call must never re-hit HF.
    httpx_mock.add_response(status_code=402)

    first = client.post("/api/v1/sentiment", json={"text": "first call"})
    second = client.post("/api/v1/sentiment", json={"text": "second call"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["inference_metadata"]["provider"] == "local"
    assert second.json()["inference_metadata"]["provider"] == "local"
    assert first.json()["inference_metadata"]["fallback_triggered"] is True
    assert second.json()["inference_metadata"]["fallback_triggered"] is True
    assert len(httpx_mock.get_requests()) == 1


def test_timeout_triggers_local_fallback(
    client: TestClient, httpx_mock, mock_local_sentiment
):
    httpx_mock.add_exception(httpx.TimeoutException("timed out"))

    response = client.post("/api/v1/sentiment", json={"text": "hello there"})

    assert response.status_code == 200
    body = response.json()
    assert body["inference_metadata"]["provider"] == "local"
    assert body["inference_metadata"]["fallback_triggered"] is True


def test_transient_error_retries_exactly_once_then_falls_back(
    client: TestClient, httpx_mock, mock_local_sentiment
):
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(status_code=503)

    response = client.post("/api/v1/sentiment", json={"text": "hello there"})

    assert response.status_code == 200
    body = response.json()
    assert body["inference_metadata"]["provider"] == "local"
    assert body["inference_metadata"]["fallback_triggered"] is True
    assert len(httpx_mock.get_requests()) == 2


def test_missing_text_returns_422(client: TestClient):
    response = client.post("/api/v1/sentiment", json={})

    assert response.status_code == 422


def test_text_over_max_length_returns_422(client: TestClient):
    response = client.post("/api/v1/sentiment", json={"text": "a" * 2001})

    assert response.status_code == 422


def test_unknown_extra_field_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/sentiment", json={"text": "hello", "extra_field": "nope"}
    )

    assert response.status_code == 422
