import pytest

import akim.llm


@pytest.fixture(autouse=True)
def _no_real_model(monkeypatch):
    """Тесты не ходят в модель, даже если в .env лежит ключ: как у проверяющего на чистом клоне."""
    monkeypatch.setattr(akim.llm, "load_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
