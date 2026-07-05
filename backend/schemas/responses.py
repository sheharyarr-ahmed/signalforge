from backend.schemas.common import InferenceMetadata, StrictModel


class LabelScore(StrictModel):
    label: str
    score: float


class SearchResult(StrictModel):
    id: int
    document: str
    similarity: float


class SentimentResponse(StrictModel):
    label: str
    scores: list[LabelScore]
    inference_metadata: InferenceMetadata


class ClassifyResponse(StrictModel):
    predicted_label: str
    scores: list[LabelScore]
    inference_metadata: InferenceMetadata


class EmbedResponse(StrictModel):
    embeddings: list[list[float]]
    count: int
    dimensions: int
    inference_metadata: InferenceMetadata


class SearchResponse(StrictModel):
    results: list[SearchResult]
    inference_metadata: InferenceMetadata
