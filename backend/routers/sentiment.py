from fastapi import APIRouter

from backend.schemas.requests import SentimentRequest
from backend.schemas.responses import SentimentResponse
from backend.services.sentiment import analyze_sentiment

router = APIRouter()


@router.post("/sentiment", response_model=SentimentResponse)
async def sentiment(req: SentimentRequest) -> SentimentResponse:
    return await analyze_sentiment(req.text)
