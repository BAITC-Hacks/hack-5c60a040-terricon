import akim
from akim.scoring import raw_score

EXAMPLE_PLAN = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]

CHEAP_PLAN = [
    {"measure": "M9", "district": "Нура"},
    {"measure": "M11", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M4", "district": "Нура"},
]


def test_baseline_score():
    b = akim.baseline()
    assert b["score"] == 52.56
    assert b["d_avg"] == 56.86
    assert b["n_crit"] == 2


def test_baseline_district_scores():
    b = akim.baseline()
    expected = {
        "Есиль": 62.99,
        "Алматы": 57.06,
        "Сарыарка": 54.65,
        "Байконур": 56.63,
        "Нура": 49.18,
    }
    actual = {d["name"]: d["d"] for d in b["districts"]}
    assert actual == expected


def test_baseline_critical_is_nura_s1_s2():
    b = akim.baseline()
    pairs = {(c["district"], c["indicator"]) for c in b["critical"]}
    assert pairs == {("Нура", "S1"), ("Нура", "S2")}


def test_example_plan_valid_with_synergy():
    e = akim.evaluate(EXAMPLE_PLAN)
    assert e["valid"]
    assert e["score"] == 56.54
    assert e["budget_used"] == 95
    assert e["budget_left"] == 5
    assert any(s["pair"] == ["M10", "M12"] and s["district"] == "Нура" for s in e["synergies"])


def test_cheapest_plan_is_valid():
    e = akim.evaluate(CHEAP_PLAN)
    assert e["valid"]
    assert e["budget_used"] == 61


def test_new_critical_m11_in_almaty():
    plan = [
        {"measure": "M11", "district": "Алматы"},
        {"measure": "M9", "district": "Нура"},
        {"measure": "M10", "district": "Нура"},
        {"measure": "M12", "district": None},
        {"measure": "M4", "district": "Байконур"},
    ]
    e = akim.evaluate(plan)
    assert e["valid"]
    hit = next(c for c in e["new_critical"] if c["district"] == "Алматы" and c["indicator"] == "T1")
    assert hit["before"] == 40.0
    assert hit["after"] == 38.25


def test_invalid_plan_returns_none_for_score_fields():
    e = akim.evaluate(EXAMPLE_PLAN[:4])
    assert not e["valid"]
    assert e["score"] is None
    assert e["delta"] is None
    assert e["d_avg"] is None
    assert e["min_district"] is None
    assert e["n_crit"] is None
    assert e["critical"] == []
    assert e["resolved_critical"] == []
    assert e["new_critical"] == []
    assert e["contributions"] == []
    assert e["synergies"] == []
    assert e["budget_used"] == 24 + 20 + 12 + 14  # M7 + M8 + M10 + M12
    for d in e["districts"]:
        assert d["d_after"] is None
        assert d["d_delta"] is None
        assert d["values_after"] is None


def test_raw_score_matches_evaluate_rounding():
    assert round(raw_score(EXAMPLE_PLAN), 2) == 56.54


def test_contributions_cover_every_plan_item():
    e = akim.evaluate(EXAMPLE_PLAN)
    measures = {c["measure"] for c in e["contributions"]}
    assert measures == {"M7", "M8", "M10", "M12", "M5"}
