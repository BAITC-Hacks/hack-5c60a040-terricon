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


def test_sensitivity_covers_all_directions():
    rows = akim.sensitivity(EXAMPLE)
    assert [r["direction"] for r in rows] == ["transport", "ecology", "social", "safety", "services"]
    for r in rows:
        assert r["best_score"] >= r["score"] - 1e-9
        assert akim.validate(r["best_plan"]) == []
