from collections import Counter
from functools import lru_cache
from itertools import combinations, product

import numpy as np

from .data import district_names, indicator_codes, indicator_weights, load_data
from .rules import normalize_plan, validate
from .scoring import raw_score

CHUNK = 20_000


@lru_cache(maxsize=1)
def _index() -> dict:
    data = load_data()
    measures = data["measures"]
    ids = [m["id"] for m in measures]
    names = list(district_names())
    codes = list(indicator_codes())
    nd, nk, nm = len(names), len(codes), len(measures)
    city = nd

    effect = np.zeros((nm, nd + 1, nd, nk))
    for mi, m in enumerate(measures):
        share = (data["horizon_quarters"] - m["lag"]) / data["horizon_quarters"]
        for code, value in m["effects"].items():
            ki = codes.index(code)
            if m["scope"] == "district":
                for di in range(nd):
                    effect[mi, di, di, ki] += value * share
            else:
                effect[mi, city, :, ki] += value * share

    hard = [(ids.index(c["pair"][0]), ids.index(c["pair"][1])) for c in data["conflicts"] if not c["same_district_only"]]
    soft = [(ids.index(c["pair"][0]), ids.index(c["pair"][1])) for c in data["conflicts"] if c["same_district_only"]]
    rows_m, rows_d = [], []
    for combo in combinations(range(nm), data["decisions"]):
        if sum(measures[i]["cost"] for i in combo) > data["budget"]:
            continue
        if max(Counter(measures[i]["direction"] for i in combo).values()) > data["max_per_direction"]:
            continue
        chosen = set(combo)
        if any(a in chosen and b in chosen for a, b in hard):
            continue
        clash = [(combo.index(a), combo.index(b)) for a, b in soft if a in chosen and b in chosen]
        options = [range(nd) if measures[i]["scope"] == "district" else (city,) for i in combo]
        for districts in product(*options):
            if any(districts[x] == districts[y] for x, y in clash):
                continue
            rows_m.append(combo)
            rows_d.append(districts)

    M = np.array(rows_m, dtype=np.int16)
    DC = np.array(rows_d, dtype=np.int16)
    base = np.array([[d["values"][k] for k in codes] for d in data["districts"]], dtype=float)
    weights = np.array([indicator_weights()[k] for k in codes])
    pop = np.array([d["population_share"] for d in data["districts"]])
    formula = data["score_formula"]
    synergies = [(ids.index(s["pair"][0]), ids.index(s["pair"][1]), codes.index(s["indicator"]), s["bonus"])
                 for s in data["synergies"]]

    n = len(M)
    score = np.empty(n)
    dist = np.empty((n, nd))
    for start in range(0, n, CHUNK):
        m, dc = M[start:start + CHUNK], DC[start:start + CHUNK]
        values = base + effect[m, dc].sum(axis=1)
        for a, b, ki, bonus in synergies:
            has_a = m == a
            both = has_a.any(axis=1) & (m == b).any(axis=1)
            where_a = (dc * has_a).sum(axis=1)
            for di in range(nd):
                values[both & (where_a == di), di, ki] += bonus
            values[both & (where_a == city), :, ki] += bonus
        np.clip(values, 0, 100, out=values)
        d_scores = values @ weights
        n_crit = (values < data["crit_threshold"]).sum(axis=(1, 2))
        score[start:start + CHUNK] = (formula["d_avg"] * (d_scores @ pop) + formula["min_d"] * d_scores.min(axis=1)
                                      - formula["crit_penalty"] * n_crit)
        dist[start:start + CHUNK] = d_scores

    cost = np.array([m["cost"] for m in measures])[M].sum(axis=1)
    order = np.argsort(-score, kind="stable")
    return {"M": M[order], "DC": DC[order], "score": score[order], "D": dist[order], "cost": cost[order],
            "ids": ids, "names": names, "codes": codes, "effect": effect, "base": base, "synergies": synergies}


def _indicator_values(ix: dict, rows: np.ndarray, district: str, indicator: str) -> np.ndarray:
    di, ki = ix["names"].index(district), ix["codes"].index(indicator)
    city = len(ix["names"])
    m, dc = ix["M"][rows], ix["DC"][rows]
    values = ix["base"][di, ki] + ix["effect"][m, dc, di, ki].sum(axis=1)
    for a, b, k, bonus in ix["synergies"]:
        if k != ki:
            continue
        has_a = m == a
        both = has_a.any(axis=1) & (m == b).any(axis=1)
        where_a = (dc * has_a).sum(axis=1)
        values[both & ((where_a == di) | (where_a == city))] += bonus
    return np.clip(values, 0, 100)


def _plan(ix: dict, row: int) -> list[dict]:
    return [{"measure": ix["ids"][mi], "district": ix["names"][di] if di < len(ix["names"]) else None}
            for mi, di in zip(ix["M"][row].tolist(), ix["DC"][row].tolist())]


def _item(ix: dict, row: int) -> dict:
    d = ix["D"][row]
    weakest = int(d.argmin())
    return {"score": round(float(ix["score"][row]), 2), "cost": int(ix["cost"][row]), "rank": row + 1,
            "weakest_district": {"name": ix["names"][weakest], "d": round(float(d[weakest]), 2)},
            "district_d": {name: round(float(v), 2) for name, v in zip(ix["names"], d)},
            "plan": _plan(ix, row)}


def total() -> int:
    return len(_index()["score"])


def search_plans(max_budget: float = 100, include=(), exclude=(), min_district_d: float | None = None,
                 min_indicators=(), maximize: str = "score", n: int = 5) -> dict:
    ix = _index()
    ids, names = ix["ids"], ix["names"]
    mask = ix["cost"] <= max_budget
    for item in include:
        if isinstance(item, dict):
            mi = ids.index(str(item["measure"]).upper())
            district = item.get("district")
            di = names.index(district) if district else len(names)
            mask &= ((ix["M"] == mi) & (ix["DC"] == di)).any(axis=1)
        else:
            mask &= (ix["M"] == ids.index(str(item).upper())).any(axis=1)
    for measure in exclude:
        mask &= ~(ix["M"] == ids.index(str(measure).upper())).any(axis=1)
    if min_district_d is not None:
        mask &= ix["D"].min(axis=1) >= min_district_d
    rows = np.flatnonzero(mask)
    for cond in min_indicators:
        if not len(rows):
            break
        values = _indicator_values(ix, rows, cond["district"], cond["indicator"])
        rows = rows[values >= cond["min"] - 1e-9]
    if maximize != "score" and maximize in names:
        di = names.index(maximize)
        rows = rows[np.argsort(-ix["D"][rows, di], kind="stable")]
    return {"plans": [_item(ix, int(r)) for r in rows[:n]], "matched": int(len(rows)), "total": len(ix["score"]),
            "complete": True}


def find_best(max_budget: float = 100, include=(), exclude=(), min_district_d: float | None = None,
              n: int = 5, maximize: str = "score", min_indicators=()) -> list[dict]:
    return search_plans(max_budget, include, exclude, min_district_d, min_indicators, maximize, n)["plans"]


def rank(plan: list[dict]) -> dict | None:
    if validate(plan):
        return None
    ix = _index()
    value = raw_score(normalize_plan(plan))
    better = int(np.count_nonzero(ix["score"] > value + 1e-9))
    return {"rank": better + 1, "total": len(ix["score"]), "best_score": round(float(ix["score"][0]), 2)}
