import pytest

import akim

EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]


def test_events_are_listed():
    ids = [e["id"] for e in akim.events()]
    assert ids == ["smog", "heating", "school_boom", "flood"]


def test_stress_test_recalculates_and_advises():
    r = akim.stress_test(EXAMPLE, "heating")
    assert r["score_before"] == 56.54 and r["score_after"] < r["score_before"]
    assert any(c["district"] == "Алматы" for c in r["new_critical"])
    assert r["advice"] is None or r["advice"]["delta"] > 0
    assert akim.validate(r["best_plan"]["plan"]) == []
    assert "Авария на теплосети" in r["text"]


def test_stress_test_needs_valid_plan_and_known_event():
    with pytest.raises(ValueError):
        akim.stress_test(EXAMPLE[:4], "smog")
    with pytest.raises(ValueError):
        akim.stress_test(EXAMPLE, "метеорит")


def test_best_variant_without_changes_is_official_best():
    assert akim.best_variant()["score"] == 57.24


def test_robustness_best_vs_most_robust():
    r = akim.robustness(EXAMPLE)
    best, robust, yours = r["best"], r["robust"], r["yours"]
    assert (best["score"], best["worst"], best["worst_event"]) == (57.24, 55.8, "Рост числа школьников")
    assert (robust["score"], robust["worst"], robust["rank"]) == (57.07, 55.82, 11)
    assert robust["worst"] >= max(best["worst"], yours["worst"]) and akim.validate(robust["plan"]) == []
    assert (yours["score"], yours["worst"], yours["worst_event"]) == (56.54, 55.26, "Авария на теплосети")
    assert r["price"] == 0.17 and r["gain"] == 0.02
    assert r["top_gain"] == {"event": "Рост числа школьников", "diff": 0.83}
    assert akim.robustness(EXAMPLE[:4])["yours"] is None


def test_sensitivity_covers_all_directions():
    rows = akim.sensitivity(EXAMPLE)
    assert [r["direction"] for r in rows] == ["transport", "ecology", "social", "safety", "services"]
    for r in rows:
        assert r["best_score"] >= r["score"] - 1e-9
        assert akim.validate(r["best_plan"]) == []
