import json

import akim
from akim.optimizer import TOP_PLANS_PATH, best_by_cost, top

EXAMPLE_PLAN = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]


def _load_top_plans():
    with open(TOP_PLANS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_precomputed_file_has_golden_total_count():
    data = _load_top_plans()
    assert data["count"] == 694395


def test_top1_matches_golden_plan():
    best = top(1)[0]
    assert best["score"] == 57.24
    assert best["cost"] == 98
    ids = {item["measure"] for item in best["plan"]}
    assert ids == {"M2", "M3", "M8", "M9", "M14"}
    nura_measures = {item["measure"] for item in best["plan"] if item["district"] == "Нура"}
    assert nura_measures == {"M3", "M8", "M9"}
    assert akim.validate(best["plan"]) == []


def test_top5_scores_match_golden_sequence():
    scores = [entry["score"] for entry in top(5)]
    assert scores == [57.24, 57.23, 57.21, 57.19, 57.17]


def test_best_by_cost_is_sorted_by_cost_and_all_valid():
    entries = best_by_cost()
    costs = [e["cost"] for e in entries]
    assert costs == sorted(costs)
    assert len(costs) == len(set(costs))
    for e in entries:
        assert akim.validate(e["plan"]) == []


def test_cheapest_entry_matches_golden_cheapest_cost():
    entries = best_by_cost()
    assert entries[0]["cost"] == 61


def test_improve_on_example_finds_a_better_plan():
    result = akim.improve(EXAMPLE_PLAN)
    assert result["better"] is True
    assert result["current_score"] == 56.54
    assert result["best"]["delta"] > 0
    assert result["best"]["score"] > 56.54
    assert akim.validate(result["best"]["plan"]) == []
    assert len(result["alternatives"]) <= 3


def test_improve_on_invalid_plan_returns_reason():
    result = akim.improve(EXAMPLE_PLAN[:4])
    assert result["better"] is False
    assert "reason" in result
