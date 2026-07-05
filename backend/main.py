from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.routers import classify, embeddings, health, sentiment
from backend.schemas.common import ErrorResponse
from backend.utils.errors import HFError, VectorStoreError
from backend.utils.logging import configure_logging


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VectorStoreError)
    async def handle_vector_store_error(
        request: Request, exc: VectorStoreError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=str(exc) or "vector store unavailable",
                error_class=type(exc).__name__,
            ).model_dump(),
        )

    @app.exception_handler(HFError)
    async def handle_hf_error(request: Request, exc: HFError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error=str(exc) or "hosted inference unavailable",
                error_class=type(exc).__name__,
            ).model_dump(),
        )


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)

    app = FastAPI(title="SignalForge", version="1.0.0", docs_url="/docs")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(sentiment.router, prefix="/api/v1")
    app.include_router(classify.router, prefix="/api/v1")
    app.include_router(embeddings.router, prefix="/api/v1")

    register_exception_handlers(app)

    return app


app = create_app()  # for `uvicorn backend.main:app`
