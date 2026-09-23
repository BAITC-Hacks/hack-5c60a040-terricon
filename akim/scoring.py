from functools import lru_cache

from .data import district_names, indicator_codes, indicator_weights, load_data, measures_by_id
from .rules import normalize_plan, validate


def _base_values():
    return {d["name"]: {k: float(v) for k, v in d["values"].items()} for d in load_data()["districts"]}


def _apply_plan(known_items, shocks=None):
    data = load_data()
    horizon = data["horizon_quarters"]
    names = district_names()
    values = _base_values()

    where = {}
    for item in known_items:
        measure = item["measure_obj"]
        district = item["district"]
        where[measure["id"]] = district
        share = (horizon - measure["lag"]) / horizon
        targets = [district] if district is not None else names
        for indicator, effect in measure["effects"].items():
            for d in targets:
                values[d][indicator] += effect * share

    applied_synergies = []
    for syn in data["synergies"]:
        a, b = syn["pair"]
        if a in where and b in where:
            target_district = where[a]
            targets = [target_district] if target_district is not None else names
            for d in targets:
                values[d][syn["indicator"]] += syn["bonus"]
            applied_synergies.append({
                "pair": [a, b],
                "district": target_district,
                "indicator": syn["indicator"],
                "bonus": syn["bonus"],
            })

    for shock in shocks or ():
        values[shock["district"]][shock["indicator"]] += shock["change"]

    for d in names:
        for k in values[d]:
            values[d][k] = min(100.0, max(0.0, values[d][k]))

    return values, applied_synergies


def _score_from_values(values, weights=None):
    data = load_data()
    weights = weights or indicator_weights()
    pop = {d["name"]: d["population_share"] for d in data["districts"]}
    threshold = data["crit_threshold"]

    D = {}
    critical = []
    for d in district_names():
        d_score = 0.0
        for k, v in values[d].items():
            d_score += weights[k] * v
            if v < threshold:
                critical.append({"district": d, "indicator": k, "value": v})
        D[d] = d_score

    d_avg = sum(pop[d] * D[d] for d in district_names())
    min_d_name = min(D, key=D.get)
    n_crit = len(critical)
    formula = data["score_formula"]
    score = formula["d_avg"] * d_avg + formula["min_d"] * D[min_d_name] - formula["crit_penalty"] * n_crit
    return score, d_avg, D, min_d_name, n_crit, critical


def _evaluate_raw(known_items, shocks=None, weights=None):
    values, synergies = _apply_plan(known_items, shocks)
    score, d_avg, D, min_d_name, n_crit, critical = _score_from_values(values, weights)
    return {
        "score": score,
        "d_avg": d_avg,
        "D": D,
        "min_d_name": min_d_name,
        "n_crit": n_crit,
        "critical": critical,
        "values": values,
        "synergies": synergies,
    }


@lru_cache
def _baseline_raw():
    return _evaluate_raw([])


def _known_items(items):
    measures = measures_by_id()
    return [
        {"measure_obj": measures[item["measure"]], "district": item["district"]}
        for item in items
        if item["measure"] in measures
    ]


def raw_score(plan):
    items = normalize_plan(plan)
    return _evaluate_raw(_known_items(items))["score"]


def _classify_critical_changes(base_values, cur_values, threshold):
    resolved, new = [], []
    for d in district_names():
        for k in indicator_codes():
            before, after = base_values[d][k], cur_values[d][k]
            was_crit, is_crit = before < threshold, after < threshold
            if was_crit and not is_crit:
                resolved.append({"district": d, "indicator": k, "before": round(before, 2), "after": round(after, 2)})
            elif not was_crit and is_crit:
                new.append({"district": d, "indicator": k, "before": round(before, 2), "after": round(after, 2)})
    return resolved, new


def contributions(plan):
    if validate(plan):
        return []
    items = normalize_plan(plan)
    known_items = _known_items(items)
    full_score = _evaluate_raw(known_items)["score"]
    result = []
    for i, ki in enumerate(known_items):
        remaining = known_items[:i] + known_items[i + 1:]
        remaining_score = _evaluate_raw(remaining)["score"]
        result.append({
            "measure": ki["measure_obj"]["id"],
            "district": ki["district"],
            "name": ki["measure_obj"]["name"],
            "cost": ki["measure_obj"]["cost"],
            "score_contribution": round(full_score - remaining_score, 2),
        })
    return result


def baseline():
    base = _baseline_raw()
    data = load_data()
    pop = {d["name"]: d["population_share"] for d in data["districts"]}
    codes = indicator_codes()
    return {
        "score": round(base["score"], 2),
        "d_avg": round(base["d_avg"], 2),
        "n_crit": base["n_crit"],
        "critical": [
            {"district": c["district"], "indicator": c["indicator"], "value": round(c["value"], 2)}
            for c in base["critical"]
        ],
        "districts": [
            {
                "name": d,
                "population_share": pop[d],
                "d": round(base["D"][d], 2),
                "values": {k: round(base["values"][d][k], 2) for k in codes},
            }
            for d in district_names()
        ],
    }


def evaluate(plan):
    items = normalize_plan(plan)
    violations = validate(plan)
    valid = len(violations) == 0
    data = load_data()
    measures = measures_by_id()
    horizon = data["horizon_quarters"]
    budget = data["budget"]
    codes = indicator_codes()
    pop = {d["name"]: d["population_share"] for d in data["districts"]}

    enriched_plan = []
    for item in items:
        measure = measures.get(item["measure"])
        entry = {"measure": item["measure"], "district": item["district"]}
        if measure:
            entry.update({
                "name": measure["name"],
                "direction": measure["direction"],
                "scope": measure["scope"],
                "cost": measure["cost"],
                "lag": measure["lag"],
                "realized_share": (horizon - measure["lag"]) / horizon,
            })
        else:
            entry.update({
                "name": None, "direction": None, "scope": None,
                "cost": None, "lag": None, "realized_share": None,
            })
        enriched_plan.append(entry)

    known_items = _known_items(items)
    budget_used = sum(ki["measure_obj"]["cost"] for ki in known_items)

    directions_count = {d["code"]: 0 for d in data["directions"]}
    for ki in known_items:
        directions_count[ki["measure_obj"]["direction"]] += 1

    base = _baseline_raw()

    result = {
        "valid": valid,
        "errors": violations,
        "plan": enriched_plan,
        "budget": budget,
        "budget_used": budget_used,
        "budget_left": budget - budget_used,
        "directions": directions_count,
    }

    if not valid:
        result.update({
            "score": None,
            "base_score": round(base["score"], 2),
            "delta": None,
            "d_avg": None,
            "base_d_avg": round(base["d_avg"], 2),
            "min_district": None,
            "n_crit": None,
            "critical": [],
            "resolved_critical": [],
            "new_critical": [],
            "contributions": [],
            "synergies": [],
            "districts": [
                {
                    "name": d,
                    "population_share": pop[d],
                    "d_before": round(base["D"][d], 2),
                    "values_before": {k: round(base["values"][d][k], 2) for k in codes},
                    "d_after": None,
                    "d_delta": None,
                    "values_after": None,
                }
                for d in district_names()
            ],
        })
        return result

    cur = _evaluate_raw(known_items)
    resolved_critical, new_critical = _classify_critical_changes(base["values"], cur["values"], data["crit_threshold"])

    result.update({
        "score": round(cur["score"], 2),
        "base_score": round(base["score"], 2),
        "delta": round(round(cur["score"], 2) - round(base["score"], 2), 2),
        "d_avg": round(cur["d_avg"], 2),
        "base_d_avg": round(base["d_avg"], 2),
        "min_district": {"name": cur["min_d_name"], "d": round(cur["D"][cur["min_d_name"]], 2)},
        "n_crit": cur["n_crit"],
        "critical": [
            {"district": c["district"], "indicator": c["indicator"], "value": round(c["value"], 2)}
            for c in cur["critical"]
        ],
        "resolved_critical": resolved_critical,
        "new_critical": new_critical,
        "contributions": contributions(plan),
        "synergies": cur["synergies"],
        "districts": [
            {
                "name": d,
                "population_share": pop[d],
                "d_before": round(base["D"][d], 2),
                "d_after": round(cur["D"][d], 2),
                "d_delta": round(round(cur["D"][d], 2) - round(base["D"][d], 2), 2),
                "values_before": {k: round(base["values"][d][k], 2) for k in codes},
                "values_after": {k: round(cur["values"][d][k], 2) for k in codes},
            }
            for d in district_names()
        ],
    })
    return result
