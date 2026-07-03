---
name: structured-logging
description: structlog JSON logging configuration and required log fields for SignalForge. Use before writing or changing backend/utils/logging.py or adding log statements.
---

# structlog JSON logging (structlog==26.1.0)

Configured once in `backend/utils/logging.py`, called from the app factory before anything logs (SPEC.md D9 — observability from commit one).

```python
import logging

import structlog

def configure_logging(log_level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
```

## Required fields on every inference request log

One `log.info("inference_complete", ...)` per request at the service layer, with exactly these keys — consistent fields are the observability story told in proposals; ad-hoc keys are the failure mode D9 exists to prevent:

```python
log.info(
    "inference_complete",
    endpoint="/api/v1/sentiment",
    model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
    provider="huggingface_api",      # or "local"
    fallback_triggered=False,
    duration_ms=412,
)
```

Error paths log `log.warning("hf_error", error_class="HFQuotaError", ...)` before routing to fallback — the fallback decision must be reconstructable from logs alone.

## Rules

- No `print()`, no stdlib `logging.getLogger` calls outside the config module.
- JSON renderer always — even in development (`ENVIRONMENT` does not change the format, only `LOG_LEVEL` changes verbosity). One format everywhere is the point.
- Never log request text bodies or secrets — endpoint, sizes, timings, and routing flags only.
