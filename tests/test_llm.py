from types import SimpleNamespace

from akim import llm


def _capture_request(monkeypatch):
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "_client", lambda: client)
    return captured


def test_reasoning_model_receives_explicit_effort(monkeypatch):
    captured = _capture_request(monkeypatch)
    llm.complete([], model="gpt-5-mini", reasoning_effort="none")
    assert captured["reasoning_effort"] == "none"


def test_non_reasoning_model_omits_effort(monkeypatch):
    captured = _capture_request(monkeypatch)
    llm.complete([], model="gpt-4o-mini", reasoning_effort="none")
    assert "reasoning_effort" not in captured
