import pytest

import akim
from akim import explainer

EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setenv("AKIM_NO_LLM", "1")


def test_template_without_key():
    r = akim.explain(EXAMPLE)
    assert r["mode"] == "template"
    assert r["strengths"] and r["risks"] and r["consequences"]
    assert "38 → 48" in " ".join(r["strengths"])
    assert "56,54" in r["text"]
    assert r["suggestion"]["score"] == 57.21
    assert r["suggestion"]["delta"] == 0.67


def test_invalid_plan_is_explained_by_rules():
    r = akim.explain(EXAMPLE[:4])
    assert r["mode"] == "template"
    assert "недопустим" in r["text"]
    assert r["risks"]


def test_template_numbers_pass_the_guard():
    res = akim.evaluate(EXAMPLE)
    f = explainer.facts(res, akim.improve(EXAMPLE))
    assert explainer.unknown_numbers(explainer.template(f), f) == []


def test_guard_catches_invented_number():
    f = explainer.facts(akim.evaluate(EXAMPLE))
    fake = {"strengths": ["Score вырос до 61,3"], "risks": [], "consequences": [], "text": "M7 в Нуре, S1 выше"}
    assert explainer.unknown_numbers(fake, f) == ["61,3"]


def test_guard_accepts_number_embedded_in_tool_text():
    payload = {"strengths": [], "risks": [], "consequences": [], "text": "Воздух был 48,75."}
    facts = {"tool_result": "Качество воздуха до мер: 48,75"}
    assert explainer.unknown_numbers(payload, facts) == []
    payload["text"] = "Воздух был 48,76."
    assert explainer.unknown_numbers(payload, facts) == ["48,76"]


def test_model_answer_with_invented_number_falls_back(monkeypatch):
    monkeypatch.setattr(explainer.llm, "enabled", lambda: True)
    monkeypatch.setattr(explainer, "_ask_model",
                        lambda f: {"strengths": ["Score 99,9"], "risks": [], "consequences": [], "text": "итог"})
    r = akim.explain(EXAMPLE)
    assert r["mode"] == "template"
    assert "99,9" in r["note"]


def test_model_error_falls_back(monkeypatch):
    monkeypatch.setattr(explainer.llm, "enabled", lambda: True)

    def boom(f):
        raise RuntimeError("нет сети")

    monkeypatch.setattr(explainer, "_ask_model", boom)
    r = akim.explain(EXAMPLE)
    assert r["mode"] == "template"
    assert r["note"]


def test_model_answer_with_real_numbers_is_accepted(monkeypatch):
    monkeypatch.setattr(explainer.llm, "enabled", lambda: True)
    monkeypatch.setattr(explainer, "_ask_model", lambda f: {
        "strengths": ["Score 56,54, прирост +3,98 к базе 52,56"], "risks": ["Нура — 52,96"],
        "consequences": [], "text": "Школа в Нуре даёт +1,45."})
    assert akim.explain(EXAMPLE)["mode"] == "llm"
