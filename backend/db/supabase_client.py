"""Supabase access for the pgvector documents store (SPEC.md D6, SPEC-AMENDMENTS.md A5-A6).

HTTPS/PostgREST only — HF Spaces block outbound traffic except 80/443/8080, so a
direct Postgres connection cannot work from the deployed Space, and supabase-py
over port 443 consumes zero of the Postgres connection budget. Never use `vecs`
or a raw connection string here.

PostgREST exposes no pgvector operators, so `match_documents` (defined in
migrations.sql) via `.rpc()` is the only supported vector-query path.

Every failure is normalized to VectorStoreError — no raw supabase-py/httpx
exception should ever reach a route handler.
"""

from functools import lru_cache

from backend.config import get_settings
from backend.utils.errors import VectorStoreError


@lru_cache(maxsize=1)
def get_supabase():
    from supabase import create_client

    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def insert_documents(rows: list[dict]) -> None:
    try:
        get_supabase().table("documents").insert(rows).execute()
    except Exception as e:
        raise VectorStoreError(f"failed to insert documents: {e}") from e


def match_documents(query_embedding: list[float], match_count: int) -> list[dict]:
    try:
        res = get_supabase().rpc(
            "match_documents",
            {"query_embedding": query_embedding, "match_count": match_count},
        ).execute()
        return res.data or []
    except Exception as e:
        raise VectorStoreError(f"failed to query match_documents: {e}") from e
