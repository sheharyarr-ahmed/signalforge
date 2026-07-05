from pydantic import ConfigDict, Field, field_validator

from backend.schemas.common import StrictModel

_MAX_DOCUMENT_LENGTH = 2000


class SentimentRequest(StrictModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Este producto es increíble, lo recomiendo totalmente",
            }
        }
    )

    text: str = Field(min_length=1, max_length=2000)


class ClassifyRequest(StrictModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": (
                    "The party of the first part agrees to indemnify and hold "
                    "harmless the party of the second part against any and all "
                    "claims arising from breach of this agreement."
                ),
                "labels": ["legal", "financial", "marketing", "technical"],
            }
        }
    )

    text: str = Field(min_length=1, max_length=2000)
    labels: list[str] = Field(min_length=2, max_length=10)


class EmbedRequest(StrictModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "documents": [
                    "Invoices are due within 30 days",
                    "The rocket launched successfully",
                    "Quarterly revenue grew 12 percent",
                ]
            }
        }
    )

    documents: list[str] = Field(min_length=1, max_length=20)

    @field_validator("documents")
    @classmethod
    def check_document_length(cls, value: list[str]) -> list[str]:
        for document in value:
            if len(document) > _MAX_DOCUMENT_LENGTH:
                raise ValueError(
                    f"each document must be at most {_MAX_DOCUMENT_LENGTH} characters"
                )
        return value


class SearchRequest(StrictModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "payment terms",
                "k": 2,
            }
        }
    )

    query: str = Field(min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=20)
