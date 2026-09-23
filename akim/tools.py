from .data import district_names, indicator_weights, load_data, measures_by_id
from .optimizer import best_by_cost
from .rules import normalize_plan, validate
from .scoring import _evaluate_raw, _known_items, baseline, evaluate

WEAK_LIMIT = 45


def frontier() -> list[dict]:
    return best_by_cost()


def compare(plan_a: list[dict], plan_b: list[dict]) -> dict:
    a, b = evaluate(plan_a), evaluate(plan_b)
    ids_a = {(p["measure"], p["district"]) for p in a["plan"]}
    ids_b = {(p["measure"], p["district"]) for p in b["plan"]}
    both_valid = a["valid"] and b["valid"]
    districts = []
    for da, db in zip(a["districts"], b["districts"]):
        if both_valid:
            districts.append({"name": da["name"], "d_a": da["d_after"], "d_b": db["d_after"],
                              "diff": round(db["d_after"] - da["d_after"], 2)})
    return {
        "a": a,
        "b": b,
        "score_diff": round(b["score"] - a["score"], 2) if both_valid else None,
        "districts": districts,
        "only_in_a": [{"measure": m, "district": d} for m, d in sorted(ids_a - ids_b, key=str)],
        "only_in_b": [{"measure": m, "district": d} for m, d in sorted(ids_b - ids_a, key=str)],
    }


def what_if(plan: list[dict], remove: str | None = None, add: dict | None = None) -> dict:
    items = normalize_plan(plan)
    if remove:
        items = [i for i in items if i["measure"] != str(remove).upper()]
    if add:
        items = items + normalize_plan([add])
    before = evaluate(plan)
    after = evaluate(items)
    delta = round(after["score"] - before["score"], 2) if before["valid"] and after["valid"] else None
    return {"before": before["score"], "after": after, "delta": delta, "new_plan": items}


def district_report(district: str, plan: list[dict] | None = None) -> dict:
    data = load_data()
    if district not in district_names():
        raise ValueError(f"Неизвестный район: {district}")
    items = normalize_plan(plan or [])
    use_plan = bool(items) and not validate(items)
    ind = {i["code"]: i["name"] for i in data["indicators"]}
    profile = next(d["profile"] for d in data["districts"] if d["name"] == district)

    if use_plan:
        res = evaluate(items)
        row = next(d for d in res["districts"] if d["name"] == district)
        values, d_now = row["values_after"], row["d_after"]
    else:
        row = next(d for d in baseline()["districts"] if d["name"] == district)
        values, d_now = row["values"], row["d"]

    order = sorted(values.items(), key=lambda kv: kv[1])
    weak = [{"indicator": k, "name": ind[k], "value": v} for k, v in order if v < WEAK_LIMIT] or \
           [{"indicator": k, "name": ind[k], "value": v} for k, v in order[:3]]

    current = _evaluate_raw(_known_items(items))
    in_plan = {i["measure"] for i in items}
    weights = indicator_weights()
    options = []
    for measure in data["measures"]:
        if measure["id"] in in_plan:
            continue
        candidate = {"measure": measure["id"], "district": district if measure["scope"] == "district" else None}
        after = _evaluate_raw(_known_items(items + [candidate]))
        d_gain = after["D"][district] - current["D"][district]
        if d_gain <= 0:
            continue
        options.append({
            "measure": measure["id"],
            "name": measure["name"],
            "scope": measure["scope"],
            "cost": measure["cost"],
            "d_gain": round(d_gain, 2),
            "score_gain": round(after["score"] - current["score"], 2),
            "fixes": [ind[k] for k in measure["effects"] if weights.get(k) and k in dict(order[:3])],
        })
    options.sort(key=lambda o: -o["score_gain"])
    ranking = sorted(((d["name"], d["d_after"] if use_plan else d["d"]) for d in
                      (evaluate(items)["districts"] if use_plan else baseline()["districts"])),
                     key=lambda x: x[1])
    return {
        "district": district,
        "profile": profile,
        "d": d_now,
        "place_from_bottom": [name for name, _ in ranking].index(district) + 1,
        "weak": weak,
        "best_measures": options[:5],
        "with_plan": use_plan,
    }
