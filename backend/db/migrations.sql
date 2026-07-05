-- SignalForge pgvector migration (Phase 1, per SPEC.md D6 / SPEC-AMENDMENTS.md A5-A7).
-- Applied manually via the Supabase SQL editor — never run by the app (D12).
-- vector(384) is locked to sentence-transformers/all-MiniLM-L6-v2 output.
-- Changing the dimension is a one-way door: it means re-embedding every row.

create extension if not exists vector with schema extensions;

create table documents (
  id bigint generated always as identity primary key,
  content text not null,
  embedding vector(384) not null,
  created_at timestamptz not null default now()
);

-- HNSW, not ivfflat (SPEC-AMENDMENTS A5): ivfflat trains centroids from existing
-- rows, so a Phase-1 index built on an empty table is degenerate. HNSW builds
-- incrementally and is Supabase's documented default.
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
