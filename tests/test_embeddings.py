"""Tests for /api/v1/embed and /api/v1/search (SPEC.md §Goal item 3, D6, A5/A6/A10).

Fully hermetic: no real SentenceTransformer load, no real Supabase/PostgREST call.
`backend.services.embedder.embed_texts` and `backend.db.supabase_client.insert_documents`
/ `match_documents` are monkeypatched per-test. The real 384-dim proof (that the
actual model produces 384-length vectors) is a separate `python -c` smoke run
outside pytest, not exercised here.
"""

from fastapi.testclient import TestClient

import backend.services.embedder as embedder
from backend.db import supabase_client

FAKE_DIM = 384


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    return [[0.1] * FAKE_DIM for _ in texts]


def test_embed_returns_384_dim_vectors_and_persists_rows(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(embedder, "embed_texts", _fake_embed_texts)

    recorded_calls: list[list[dict]] = []

    def fake_insert_documents(rows: list[dict]) -> None:
        recorded_calls.append(rows)

    monkeypatch.setattr(supabase_client, "insert_documents", fake_insert_documents)

    documents = [
        "Invoices are due within 30 days",
        "The rocket launched successfully",
        "Quarterly revenue grew 12 percent",
    ]

    response = client.post("/api/v1/embed", json={"documents": documents})

    assert response.status_code == 200
    body = response.json()

    assert body["count"] == 3
    assert body["dimensions"] == 384
    assert len(body["embeddings"]) == 3
    assert len(body["embeddings"][0]) == 384
    assert body["inference_metadata"]["provider"] == "local"
    assert body["inference_metadata"]["model"] == embedder.EMBED_MODEL
    assert body["inference_metadata"]["confidence"] is None

    assert len(recorded_calls) == 1
    rows = recorded_calls[0]
    assert len(rows) == 3
    for row, doc, vector in zip(rows, documents, body["embeddings"]):
        assert row["content"] == doc
        assert row["embedding"] == vector


def test_search_returns_top_k_ordered_by_descending_similarity(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(embedder, "embed_texts", _fake_embed_texts)

    fake_rows = [
        {"id": 1, "content": "Invoices are due within 30 days", "similarity": 0.91},
        {"id": 2, "content": "The rocket launched", "similarity": 0.42},
    ]

    def fake_match_documents(query_embedding: list[float], match_count: int) -> list[dict]:
        return fake_rows

    monkeypatch.setattr(supabase_client, "match_documents", fake_match_documents)

    response = client.post("/api/v1/search", json={"query": "payment terms", "k": 2})

    assert response.status_code == 200
    body = response.json()

    results = body["results"]
    assert len(results) == 2
    assert results[0]["document"] == "Invoices are due within 30 days"
    assert results[0]["similarity"] >= results[1]["similarity"]
    assert body["inference_metadata"]["provider"] == "local"
    assert body["inference_metadata"]["confidence"] is None


def test_search_on_empty_store_returns_empty_results_not_an_error(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(embedder, "embed_texts", _fake_embed_texts)

    def fake_match_documents(query_embedding: list[float], match_count: int) -> list[dict]:
        return []

    monkeypatch.setattr(supabase_client, "match_documents", fake_match_documents)

    response = client.post("/api/v1/search", json={"query": "anything", "k": 5})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_k_below_lower_bound_is_rejected_by_schema(client: TestClient) -> None:
    response = client.post("/api/v1/search", json={"query": "payment terms", "k": 0})

    assert response.status_code == 422


def test_search_k_above_upper_bound_is_rejected_by_schema(client: TestClient) -> None:
    response = client.post("/api/v1/search", json={"query": "payment terms", "k": 21})

    assert response.status_code == 422
