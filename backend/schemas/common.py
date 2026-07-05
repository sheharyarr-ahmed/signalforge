from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class InferenceMetadata(StrictModel):
    model: str
    provider: Literal["huggingface_api", "local"]
    processing_time_ms: int
    fallback_triggered: bool
    confidence: float | None


class ErrorResponse(StrictModel):
    error: str
    error_class: str | None = None
