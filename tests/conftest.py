import os

os.environ.setdefault("HF_API_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-key")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.schemas.responses import LabelScore  # noqa: E402
from backend.services import sentiment as sentiment_service  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_hf_quota_state():
    """Clear the in-process HF quota cache (SPEC-AMENDMENTS.md A2) before
    every test so quota state never leaks between test cases.
    """
    sentiment_service.reset_quota_state()
    yield
    sentiment_service.reset_quota_state()


@pytest.fixture
def mock_local_sentiment(monkeypatch: pytest.MonkeyPatch) -> list[LabelScore]:
    """Patch the local CPU fallback so fallback tests never load the real
    ~1 GB sentiment model. Returns a canned, already-lowercased score list.
    """
    canned = [
        LabelScore(label="positive", score=0.9),
        LabelScore(label="neutral", score=0.07),
        LabelScore(label="negative", score=0.03),
    ]

    def _fake_run_local_sentiment(text: str) -> list[LabelScore]:
        return canned

    monkeypatch.setattr(
        sentiment_service, "_run_local_sentiment", _fake_run_local_sentiment
    )
    return canned
