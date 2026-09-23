"""Independent Decimal reference vs scalar and NumPy search calculations.

The reference implements the published formula directly from data; it does not
call the production effect, synergy, clipping, or scoring helpers.
"""

from decimal import Decimal
import random

import numpy as np
import pytest

import akim
from akim.data import load_data, indicator_weights
from akim.scoring import _evaluate_raw, _known_items
from akim.search import _index, _plan, _score_rows


def reference(plan, shocks=(), weights=None):
    data = load_data()
    number = lambda value: Decimal(str(value))
    values = {d["name"]: {k: number(v) for k, v in d["values"].items()} for d in data["districts"]}
    measures = {m["id"]: m for m in data["measures"]}
    selected = {item["measure"]: item["district"] for item in plan}
    horizon = number(data["horizon_quarters"])
    for item in plan:
        measure = measures[item["measure"]]
        fraction = (horizon - number(measure["lag"])) / horizon
        targets = values if measure["scope"] == "city" else [item["district"]]
        for district in targets:
            for code, effect in measure["effects"].items():
                values[district][code] += number(effect) * fraction
    for synergy in data["synergies"]:
        first, second = synergy["pair"]
        if first in selected and second in selected:
            targets = values if selected[first] is None else [selected[first]]
            for district in targets:
                values[district][synergy["indicator"]] += number(synergy["bonus"])
    for shock in shocks:
        values[shock["district"]][shock["indicator"]] += number(shock["change"])
    for district in values.values():
        for code in district:
            district[code] = max(Decimal(0), min(Decimal(100), district[code]))
    weights = weights or indicator_weights()
    districts = {name: sum(number(weights[k]) * v for k, v in row.items()) for name, row in values.items()}
    average = sum(number(d["population_share"]) * districts[d["name"]] for d in data["districts"])
    critical = sum(v < number(data["crit_threshold"]) for row in values.values() for v in row.values())
    formula = data["score_formula"]
    score = number(formula["d_avg"]) * average + number(formula["min_d"]) * min(districts.values()) - number(formula["crit_penalty"]) * critical
    return float(score), {k: float(v) for k, v in districts.items()}, critical


@pytest.fixture(scope="module")
def sampled_index():
    index = _index()
    assert len(index["score"]) == 694395
    # Leaders, tail, and fixed-seed samples throughout all feasible plans.
    rows = sorted(set(range(15)) | {len(index["score"]) - 1} |
                  set(random.Random(20260923).sample(range(len(index["score"])), 128)))
    subset = {**index, "M": index["M"][rows], "DC": index["DC"][rows]}
    return index, rows, subset


@pytest.mark.parametrize("variant", ["normal", "smog", "heating", "school_boom", "flood", "clipping", "weights"])
def test_reference_scalar_and_vector_agree(sampled_index, variant):
    index, rows, subset = sampled_index
    shocks = []
    weights = indicator_weights()
    if variant in {"smog", "heating", "school_boom", "flood"}:
        shocks = next(e["shocks"] for e in akim.events() if e["id"] == variant)
    elif variant == "clipping":
        shocks = [{"district": "Нура", "indicator": "S1", "change": -200},
                  {"district": "Есиль", "indicator": "T1", "change": 200}]
    elif variant == "weights":
        weights = {key: value * (1.2 if key.startswith("S") else 1) for key, value in weights.items()}
        total = sum(weights.values())
        weights = {key: value / total for key, value in weights.items()}
    base = index["base"].copy()
    for shock in shocks:
        base[index["names"].index(shock["district"]), index["codes"].index(shock["indicator"])] += shock["change"]
    vector_scores, vector_districts = _score_rows(subset, base, np.array([weights[k] for k in index["codes"]]))
    for position, row in enumerate(rows):
        plan = _plan(index, row)
        assert akim.validate(plan) == []
        expected, districts, critical = reference(plan, shocks, weights)
        scalar = _evaluate_raw(_known_items(plan), shocks, weights)
        assert scalar["score"] == pytest.approx(expected, abs=1e-10, rel=0)
        assert vector_scores[position] == pytest.approx(expected, abs=1e-10, rel=0)
        assert scalar["n_crit"] == critical
        for i, name in enumerate(index["names"]):
            assert scalar["D"][name] == pytest.approx(districts[name], abs=1e-10, rel=0)
            assert vector_districts[position, i] == pytest.approx(districts[name], abs=1e-10, rel=0)


def test_cached_top_scores_are_recalculated():
    for entry in akim.top(50):
        assert akim.validate(entry["plan"]) == []
        score, _, _ = reference(entry["plan"])
        assert entry["score"] == round(score, 2)
