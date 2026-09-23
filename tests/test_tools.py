import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

import akim
from akim import search, voice

EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]
BEST = [
    {"measure": "M2", "district": None},
    {"measure": "M3", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M9", "district": "Нура"},
    {"measure": "M14", "district": None},
]


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setenv("AKIM_NO_LLM", "1")


def test_search_index_matches_reference_scoring():
    assert akim.total() == 694395
    ix = search._index()
    for row in random.Random(7).sample(range(akim.total()), 200):
        assert abs(ix["score"][row] - akim.raw_score(search._plan(ix, row))) < 1e-9
    top_file = json.loads(Path("data/top_plans.json").read_text(encoding="utf-8"))["top"][0]
    best = akim.find_best(n=1)[0]
    assert best["score"] == top_file["score"] == 57.24
    assert best["plan"] == BEST and best["rank"] == 1


def test_find_best_respects_constraints():
    cheap = akim.find_best(max_budget=80, n=10)
    assert cheap and all(p["cost"] <= 80 for p in cheap)
    assert [p["score"] for p in cheap] == sorted((p["score"] for p in cheap), reverse=True)
    assert all(all(i["measure"] != "M3" for i in p["plan"]) for p in akim.find_best(exclude=["M3"], n=10))
    with_school = akim.find_best(include=[{"measure": "M7", "district": "Есиль"}], n=5)
    assert all({"measure": "M7", "district": "Есиль"} in p["plan"] for p in with_school)
    floor = akim.find_best(min_district_d=55, n=5)
    assert floor and all(p["weakest_district"]["d"] >= 55 for p in floor)
    for p in cheap + floor:
        assert akim.validate(p["plan"]) == []


def test_rank_of_plans():
    assert akim.rank(BEST)["rank"] == 1
    place = akim.rank(EXAMPLE)
    assert place["total"] == 694395 and 1 < place["rank"] < 1000
    assert akim.rank(EXAMPLE[:4]) is None


def test_compare_and_what_if():
    c = akim.compare(EXAMPLE, BEST)
    assert c["score_diff"] == 0.7
    assert {"measure": "M5", "district": "Сарыарка"} in c["only_in_a"]
    w = akim.what_if(EXAMPLE, remove="M5", add={"measure": "M3", "district": "Нура"})
    assert w["after"]["valid"] and w["after"]["score"] == 57.21 and w["delta"] == 0.67
    broken = akim.what_if(EXAMPLE, add={"measure": "M9", "district": "Нура"})
    assert not broken["after"]["valid"] and broken["delta"] is None


def test_district_report_finds_pain_and_cure():
    r = akim.district_report("Нура")
    names = {w["name"]: w["value"] for w in r["weak"]}
    assert names["Школы и детсады"] == 38 and names["Поликлиники и первичная медпомощь"] == 35
    assert r["place_from_bottom"] == 1
    gains = [m["score_gain"] for m in r["best_measures"]]
    assert gains == sorted(gains, reverse=True) and gains[0] > 0
    with pytest.raises(ValueError):
        akim.district_report("Нью-Йорк")


def test_brief_and_frontier():
    text = akim.brief(EXAMPLE)
    assert "Паспорт сценария" in text and "56,54" in text and "566 из 694 395" in text
    assert "недопустим" in akim.brief(EXAMPLE[:4])
    f = akim.frontier()
    assert f[-1]["cost"] <= 100 and max(p["score"] for p in f) == 57.24


def test_voice_needs_key():
    with pytest.raises(RuntimeError, match="ключом"):
        akim.transcribe(b"RIFF")


def test_voice_hints_district_names(monkeypatch):
    seen = {}

    class Transcriptions:
        def create(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(text=" Что с Нурой? ")

    monkeypatch.setattr(voice.llm, "enabled", lambda: True)
    monkeypatch.setattr(voice.llm, "_client",
                        lambda: SimpleNamespace(audio=SimpleNamespace(transcriptions=Transcriptions())))
    assert akim.transcribe(b"RIFF") == "Что с Нурой?"
    assert "Нура" in seen["prompt"] and "Сарыарка" in seen["prompt"] and seen["language"] == "ru"
