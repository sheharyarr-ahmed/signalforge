---
name: pydantic-schemas
description: Pydantic v2 strict-mode schema and Settings conventions for SignalForge. Use before writing or changing anything in backend/schemas/ or backend/config.py.
---

# Pydantic v2 strict schemas (pydantic==2.13.4, pydantic-settings==2.14.2)

## Strict mode everywhere (SPEC.md D8)

```python
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
```

Every request, response, and nested schema inherits from a strict base. No `Any`, no implicit coercion, no silently-ignored extra fields.

## Constraints live in the schema, never in handlers

Locked bounds (SPEC-AMENDMENTS.md A9 — these are the public-endpoint security posture):

| Field | Bound |
|---|---|
| sentiment / classify text | `min_length=1, max_length=2000` |
| classify labels | `min_length=2, max_length=10` items |
| embed documents | 1–20 per request, each ≤ 2000 chars |
| search query | `min_length=1, max_length=500` |
| search k | `ge=1, le=20` |

```python
class ClassifyRequest(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    labels: list[str] = Field(min_length=2, max_length=10)
```

## InferenceMetadata (`backend/schemas/common.py`)

```python
from typing import Literal

class InferenceMetadata(StrictModel):
    model: str                      # full HF repo id, always
    provider: Literal["huggingface_api", "local"]
    processing_time_ms: int
    fallback_triggered: bool
    confidence: float | None       # top-label score; None for embed/search
```

## Settings (`backend/config.py`)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    hf_api_token: str
    supabase_url: str
    supabase_service_key: str
    environment: str = "development"
    log_level: str = "INFO"
```

Cached accessor (`@lru_cache def get_settings()`), injected via `Depends` — the only env boundary in the codebase.
