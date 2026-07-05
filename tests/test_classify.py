"""Tests for POST /api/v1/classify: happy path, custom label sets, label-count
bounds, and the no-fallback error contract (SPEC.md D5/D8, SPEC-AMENDMENTS.md A2/A8/A9).
"""

import httpx
from fastapi.testclient import TestClient

_LABELS_PAYLOAD = {"text": "hello", "labels": ["legal", "financial"]}


def test_happy_path_returns_winning_label(client: TestClient, httpx_mock):
    httpx_mock.add_response(
        json=[
            {"label": "legal", "score": 0.8},
            {"label": "financial", "score": 0.1},
            {"label": "marketing", "score": 0.05},
            {"label": "technical", "score": 0.05},
        ]
    )

    response = client.post(
        "/api/v1/classify",
        json={
            "text": (
                "The party of the first part agrees to indemnify and hold "
                "harmless the party of the second part."
            ),
            "labels": ["legal", "financial", "marketing", "technical"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["predicted_label"] == "legal"
    assert body["inference_metadata"]["provider"] == "huggingface_api"
    assert body["inference_metadata"]["fallback_triggered"] is False
    assert body["inference_metadata"]["model"] == "facebook/bart-large-mnli"


def test_custom_labels_resolve_to_max_score_label(client: TestClient, httpx_mock):
    httpx_mock.add_response(
        json=[
            {"label": "sports", "score": 0.15},
            {"label": "politics", "score": 0.75},
            {"label": "science", "score": 0.10},
        ]
    )

    response = client.post(
        "/api/v1/classify",
        json={
            "text": "The senator introduced a new bill in congress today.",
            "labels": ["sports", "politics", "science"],
        },
    )

    assert response.status_code == 200
    assert response.json()["predicted_label"] == "politics"


def test_single_label_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/classify", json={"text": "hello", "labels": ["legal"]}
    )

    assert response.status_code == 422


def test_eleven_labels_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/classify",
        json={"text": "hello", "labels": [f"label{i}" for i in range(11)]},
    )

    assert response.status_code == 422


def test_text_over_max_length_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/classify",
        json={"text": "a" * 2001, "labels": ["legal", "financial"]},
    )

    assert response.status_code == 422


def test_quota_error_returns_503_with_no_fallback(client: TestClient, httpx_mock):
    httpx_mock.add_response(status_code=402)

    response = client.post("/api/v1/classify", json=_LABELS_PAYLOAD)

    assert response.status_code == 503
    body = response.json()
    assert body["error_class"] == "HFQuotaError"
    assert "predicted_label" not in body
    assert "fallback_triggered" not in body


def test_rate_limit_returns_503_with_no_fallback(client: TestClient, httpx_mock):
    httpx_mock.add_response(status_code=429)

    response = client.post("/api/v1/classify", json=_LABELS_PAYLOAD)

    assert response.status_code == 503
    body = response.json()
    assert body["error_class"] == "HFRateLimitError"
    assert "predicted_label" not in body


def test_timeout_returns_503_with_no_fallback(client: TestClient, httpx_mock):
    httpx_mock.add_exception(httpx.TimeoutException("timed out"))

    response = client.post("/api/v1/classify", json=_LABELS_PAYLOAD)

    assert response.status_code == 503
    body = response.json()
    assert body["error_class"] == "HFTimeoutError"
    assert "predicted_label" not in body


def test_transient_error_retries_once_then_returns_503(
    client: TestClient, httpx_mock
):
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(status_code=503)

    response = client.post("/api/v1/classify", json=_LABELS_PAYLOAD)

    assert response.status_code == 503
    body = response.json()
    assert body["error_class"] == "HFTransientError"
    assert "predicted_label" not in body
    assert len(httpx_mock.get_requests()) == 2
