from fastapi import APIRouter

from backend.schemas.requests import ClassifyRequest
from backend.schemas.responses import ClassifyResponse
from backend.services.classifier import classify_text

router = APIRouter()


@router.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest) -> ClassifyResponse:
    return await classify_text(req.text, req.labels)
