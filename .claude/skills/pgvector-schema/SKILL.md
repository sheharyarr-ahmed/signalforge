---
name: pgvector-schema
description: Supabase pgvector schema, HNSW indexing, and the match_documents RPC pattern for SignalForge semantic search. Use before writing or changing migrations.sql, supabase_client.py, or the /search path.
---

# Supabase pgvector (verified 2026-07)

## Hard constraint: HTTPS only

HF Spaces block outbound traffic except ports 80/443/8080 — a direct Postgres connection (5432/6543) **cannot work from the deployed Space**. All access goes through supabase-py over PostgREST (port 443). This consumes zero of the Postgres connection budget. Never use `vecs` (requires direct Postgres) or raw connection strings.

Pin `supabase==2.31.0` — a breaking 3.0 alpha is already on PyPI.

## Schema (migrations.sql — applied manually via the Supabase SQL editor, never from the app)

```sql
create extension if not exists vector with schema extensions;

create table documents (
  id bigint generated always as identity primary key,
  content text not null,
  embedding vector(384) not null,
  created_at timestamptz not null default now()
);

-- HNSW, not ivfflat: ivfflat trains centroids from existing rows, so an index
-- created by the Phase-1 migration on an empty table is degenerate. HNSW builds
-- incrementally and is Supabase's documented default recommendation.
create index on documents using hnsw (embedding vector_cosine_ops);

create or replace function match_documents(
  query_embedding vector(384),
  match_count int
) returns table (id bigint, content text, similarity float)
language sql stable as $$
  select d.id, d.content, 1 - (d.embedding <=> query_embedding) as similarity
  from documents d
  order by d.embedding <=> query_embedding
  limit match_count;
$$;
```

The `match_documents` function is mandatory — PostgREST exposes no pgvector operators, so RPC is the only supported query path from supabase-py.

## Python patterns

```python
# insert — embeddings as plain Python float lists
supabase.table("documents").insert({"content": text, "embedding": vector}).execute()

# search — top-k cosine via RPC
res = supabase.rpc("match_documents", {"query_embedding": vector, "match_count": k}).execute()
```

`vector(384)` is locked to all-MiniLM-L6-v2 output — changing dimensionality means re-embedding everything (one-way door, SPEC.md D6). Free-tier note: the project pauses after ~7 idle days and resume is manual — see SPEC-AMENDMENTS.md A7 before any demo.
