"""POST /api/v1/embed, POST /api/v1/search (SPEC.md §Goal item 3).

Handlers stay thin — all orchestration (embedding, persistence, RPC query,
inference_metadata construction) lives in backend/services/embedder.py.
"""

from fastapi import APIRouter

from backend.schemas.requests import EmbedRequest, SearchRequest
from backend.schemas.responses import EmbedResponse, SearchResponse
from backend.services.embedder import embed_and_store, search_documents

router = APIRouter()


@router.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    return await embed_and_store(req.documents)


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    return await search_documents(req.query, req.k)
