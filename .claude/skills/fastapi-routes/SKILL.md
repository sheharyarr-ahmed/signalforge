---
name: fastapi-routes
description: FastAPI app-factory, router, and exception-handler conventions for SignalForge. Use before adding or changing routes, main.py, or error responses.
---

# FastAPI conventions (fastapi==0.139.0)

## App factory (`backend/main.py`)

```python
def create_app() -> FastAPI:
    app = FastAPI(title="SignalForge", version="1.0.0", docs_url="/docs")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(health.router)
    app.include_router(sentiment.router, prefix="/api/v1")
    app.include_router(classify.router, prefix="/api/v1")
    app.include_router(embeddings.router, prefix="/api/v1")
    register_exception_handlers(app)
    return app

app = create_app()  # uvicorn backend.main:app
```

## Conventions

- One router per file in `backend/routers/`; endpoints declared with `response_model=` so Swagger (the demo surface — there is no frontend) shows exact contracts.
- Handlers are thin: schema-validated input → service call → typed response. Any `if`-logic beyond wiring belongs in `backend/services/`.
- All handlers `async def`; services expose async APIs. CPU-bound local inference goes through `run_in_executor`/`asyncio.to_thread` so the event loop never blocks on torch.
- Exception handlers (registered once in main.py) map typed errors to `ErrorResponse`: `VectorStoreError` → 502, exhausted HF paths for classify → 503 with the honest quota message, `RequestValidationError` → FastAPI's default 422. Never leak stack traces.
- `GET /health` returns `{"status": "ok"}` with zero dependencies — no model load, no DB call, no HF call (it's the keep-alive and wake-check target).
- Swagger examples: give every request schema a realistic `json_schema_extra` example so the 60-second demo recording needs zero typing.
