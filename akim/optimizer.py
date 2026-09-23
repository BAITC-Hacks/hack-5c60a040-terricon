import json
from functools import lru_cache
from itertools import combinations, product
from pathlib import Path

from .data import district_names, load_data
from .rules import normalize_plan, validate
from .scoring import contributions, raw_score

TOP_PLANS_PATH = Path(__file__).resolve().parent.parent / "data" / "top_plans.json"


@lru_cache
def _top_plans_data():
    with open(TOP_PLANS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def top(n=5):
    return _top_plans_data()["top"][:n]


def best_by_cost():
    return _top_plans_data()["best_by_cost"]


def improve(plan):
    if validate(plan):
        return {"better": False, "reason": "план невалиден, нечего улучшать"}

    items = normalize_plan(plan)
    current_score = raw_score(items)
    current_score_r = round(current_score, 2)
    data = load_data()
    names = district_names()
    current_ids = {item["measure"] for item in items}

    candidates = []
    for i, item in enumerate(items):
        for measure in data["measures"]:
            if measure["id"] in current_ids and measure["id"] != item["measure"]:
                continue
            district_options = list(names) if measure["scope"] == "district" else [None]
            for d in district_options:
                if measure["id"] == item["measure"] and d == item["district"]:
                    continue
                new_items = items[:i] + [{"measure": measure["id"], "district": d}] + items[i + 1:]
                if validate(new_items):
                    continue
                new_score = raw_score(new_items)
                candidates.append({
                    "replace": {"measure": item["measure"], "district": item["district"]},
                    "with": {"measure": measure["id"], "district": d},
                    "score": round(new_score, 2),
                    "delta": round(round(new_score, 2) - current_score_r, 2),
                    "plan": new_items,
                })

    if not candidates:
        return {"better": False, "current_score": current_score_r, "best": None, "alternatives": []}

    candidates.sort(key=lambda c: -c["score"])
    best = candidates[0]
    return {
        "better": best["score"] > current_score_r,
        "current_score": current_score_r,
        "best": best,
        "alternatives": candidates[1:4],
    }


def precompute():
    data = load_data()
    measures = data["measures"]
    names = list(district_names())
    budget = data["budget"]
    decisions = data["decisions"]

    valid_plans = []
    for combo in combinations(measures, decisions):
        cost = sum(m["cost"] for m in combo)
        if cost > budget:
            continue
        options = [names if m["scope"] == "district" else [None] for m in combo]
        for district_choice in product(*options):
            plan = [{"measure": m["id"], "district": d} for m, d in zip(combo, district_choice)]
            if validate(plan):
                continue
            score = raw_score(plan)
            valid_plans.append((score, cost, plan))

    valid_plans.sort(key=lambda x: -x[0])
    top_50 = [{"score": round(s, 2), "cost": c, "plan": p} for s, c, p in valid_plans[:50]]

    best_per_cost = {}
    for s, c, p in valid_plans:
        if c not in best_per_cost or s > best_per_cost[c][0]:
            best_per_cost[c] = (s, p)
    best_by_cost_list = [
        {"cost": c, "score": round(s, 2), "plan": p}
        for c, (s, p) in sorted(best_per_cost.items())
    ]

    return {
        "count": len(valid_plans),
        "top": top_50,
        "best_by_cost": best_by_cost_list,
    }
