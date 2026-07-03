---
name: sentence-transformers
description: Local embedding generation with sentence-transformers/all-MiniLM-L6-v2 for SignalForge — lazy singleton, normalization, and Docker pre-baking. Use before writing or changing embedder.py or the Dockerfile's model-download step.
---

# sentence-transformers local embeddings (verified 2026-07)

Pins: `sentence-transformers==5.6.0`, `torch==2.12.1` (CPU wheels — Docker installs torch from `https://download.pytorch.org/whl/cpu` FIRST, or PyPI resolution pulls multi-GB CUDA wheels).

Model: `sentence-transformers/all-MiniLM-L6-v2` — 384 dimensions, ~87 MiB download, the industry-standard free embedding (D5, locked). Always report the **full repo id** in `inference_metadata.model`.

## Lazy singleton (RAM discipline, not download discipline)

```python
from functools import lru_cache
from sentence_transformers import SentenceTransformer

@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")

def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = get_model().encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]
```

- Never load at import time (slows test collection and `/health`); never load per request.
- `normalize_embeddings=True` — cosine similarity assumes unit vectors; keep insert and query paths identical.
- `.tolist()` before handing to supabase-py (PostgREST wants plain float lists, not ndarrays).

## Docker pre-baking is mandatory

Space disk is ephemeral — anything downloaded at runtime is lost on every restart, so the Dockerfile downloads model weights at **build time** into `HF_HOME=/home/user/.cache/huggingface`. The lazy singleton then loads from local cache only; no network fetch ever happens at runtime. Same applies to the ~1.04 GiB sentiment fallback model. See the Dockerfile and SPEC-AMENDMENTS.md A6.

## Tests

`tests/test_embeddings.py` asserts: vector length == 384, deterministic output for identical input, and no model load during test collection (mock or fixture-scope the singleton — CI-less local runs still shouldn't pay a model load unless the test needs it).
