"""Local embeddings + semantic search orchestration (SPEC.md D5/D6, A5/A6/A10).

Embeddings are local-only: sentence-transformers/all-MiniLM-L6-v2, 384 dimensions,
CPU. No embedding API of any kind — this is the "no lock-in" proof, so `provider`
is always "local" and `confidence` is always None on these paths (embeddings have
no confidence score, SPEC-AMENDMENTS.md A10).

The model is a lazy singleton: first request pays the load, later requests reuse
it. Never import sentence_transformers at module import time (it would slow test
collection and health checks) and never load per request.
"""

import asyncio
import time
from functools import lru_cache

import structlog

from backend.db import supabase_client
from backend.schemas.common import InferenceMetadata
from backend.schemas.responses import EmbedResponse, SearchResponse, SearchResult

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384

log = structlog.get_logger()


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL, device="cpu")


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = get_model().encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


async def embed_and_store(documents: list[str]) -> EmbedResponse:
    start = time.perf_counter()

    vectors = await asyncio.to_thread(embed_texts, documents)

    await asyncio.to_thread(
        supabase_client.insert_documents,
        [{"content": c, "embedding": v} for c, v in zip(documents, vectors)],
    )

    duration_ms = int((time.perf_counter() - start) * 1000)
    metadata = InferenceMetadata(
        model=EMBED_MODEL,
        provider="local",
        processing_time_ms=duration_ms,
        fallback_triggered=False,
        confidence=None,
    )

    log.info(
        "inference_complete",
        endpoint="/api/v1/embed",
        model=EMBED_MODEL,
        provider="local",
        fallback_triggered=False,
        duration_ms=duration_ms,
    )

    return EmbedResponse(
        embeddings=vectors,
        count=len(vectors),
        dimensions=DIM,
        inference_metadata=metadata,
    )


async def search_documents(query: str, k: int) -> SearchResponse:
    start = time.perf_counter()

    query_vector = (await asyncio.to_thread(embed_texts, [query]))[0]
    rows = await asyncio.to_thread(supabase_client.match_documents, query_vector, k)

    results = [
        SearchResult(id=row["id"], document=row["content"], similarity=row["similarity"])
        for row in rows
    ]

    duration_ms = int((time.perf_counter() - start) * 1000)
    metadata = InferenceMetadata(
        model=EMBED_MODEL,
        provider="local",
        processing_time_ms=duration_ms,
        fallback_triggered=False,
        confidence=None,
    )

    log.info(
        "inference_complete",
        endpoint="/api/v1/search",
        model=EMBED_MODEL,
        provider="local",
        fallback_triggered=False,
        duration_ms=duration_ms,
    )

    return SearchResponse(results=results, inference_metadata=metadata)
