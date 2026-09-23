import json
from functools import lru_cache
from pathlib import Path

from .data import direction_names, district_names, indicator_weights, load_data
from .explainer import fmt, fmt_signed
from .rules import normalize_plan, validate
from .scoring import _evaluate_raw, _known_items
from .search import best_variant

EVENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "events.json"
PRIORITY_BOOST = 1.2


@lru_cache(maxsize=1)
def events() -> list[dict]:
    return json.loads(EVENTS_PATH.read_text(encoding="utf-8"))


def _event(event_id: str) -> dict:
    for ev in events():
        if ev["id"] == event_id:
            return ev
    raise ValueError(f"Неизвестное событие: {event_id}")


def _best_swap(items: list[dict], shocks: list[dict]) -> dict | None:
    data = load_data()
    names = district_names()
    current = _evaluate_raw(_known_items(items), shocks)["score"]
    ids = {i["measure"] for i in items}
    best = None
    for i, item in enumerate(items):
        for m in data["measures"]:
            if m["id"] in ids and m["id"] != item["measure"]:
                continue
            for d in (names if m["scope"] == "district" else (None,)):
                if m["id"] == item["measure"] and d == item["district"]:
                    continue
                cand = items[:i] + [{"measure": m["id"], "district": d}] + items[i + 1:]
                if validate(cand):
                    continue
                score = _evaluate_raw(_known_items(cand), shocks)["score"]
                if best is None or score > best["raw"]:
                    best = {"raw": score, "replace": item, "with": {"measure": m["id"], "district": d}, "plan": cand}
    if not best or round(best["raw"], 2) <= round(current, 2):
        return None
    return {"replace": best["replace"], "with": best["with"], "plan": best["plan"], "score": round(best["raw"], 2),
            "delta": round(round(best["raw"], 2) - round(current, 2), 2)}


def stress_test(plan: list[dict], event_id: str) -> dict:
    ev = _event(event_id)
    items = normalize_plan(plan)
    if validate(items):
        raise ValueError("Сначала соберите допустимый набор из 5 решений")
    ind = {i["code"]: i["name"] for i in load_data()["indicators"]}
    calm = _evaluate_raw(_known_items(items))
    hit = _evaluate_raw(_known_items(items), ev["shocks"])
    calm_crit = {(c["district"], c["indicator"]) for c in calm["critical"]}
    new_critical = [{"district": c["district"], "indicator": c["indicator"], "name": ind[c["indicator"]],
                     "value": round(c["value"], 2)} for c in hit["critical"]
                    if (c["district"], c["indicator"]) not in calm_crit]
    advice = _best_swap(items, ev["shocks"])
    best = best_variant(shocks=ev["shocks"])
    before, after = round(calm["score"], 2), round(hit["score"], 2)
    text = f"«{ev['name']}»: Score сценария {fmt(before)} → {fmt(after)} ({fmt_signed(round(after - before, 2))})."
    if new_critical:
        text += " Новые провалы ниже 40: " + ", ".join(f"{c['district']} — {c['name'].lower()} {fmt(c['value'])}"
                                                   for c in new_critical) + "."
    if advice:
        text += (f" Совет: заменить {advice['replace']['measure']} ({advice['replace']['district'] or 'весь город'}) "
                 f"на {advice['with']['measure']} ({advice['with']['district'] or 'весь город'}) — "
                 f"{fmt(advice['score'])} ({fmt_signed(advice['delta'])}).")
    else:
        text += " Одной заменой лучше не сделать — сценарий устойчив к этому событию."
    text += f" Лучший набор при таком событии даёт {fmt(best['score'])}."
    return {"event": ev, "score_before": before, "score_after": after, "delta": round(after - before, 2),
            "n_crit_after": hit["n_crit"], "new_critical": new_critical, "advice": advice, "best_plan": best,
            "text": text}


def _boosted_weights(direction: str) -> dict:
    data = load_data()
    base = indicator_weights()
    boosted = {i["code"]: base[i["code"]] * (PRIORITY_BOOST if i["direction"] == direction else 1.0)
               for i in data["indicators"]}
    total = sum(boosted.values())
    return {k: v / total for k, v in boosted.items()}


def sensitivity(plan: list[dict]) -> list[dict]:
    items = normalize_plan(plan)
    if validate(items):
        raise ValueError("Сначала соберите допустимый набор из 5 решений")
    names = direction_names()
    out = []
    official_best = best_variant()
    for code, name in names.items():
        w = _boosted_weights(code)
        score = _evaluate_raw(_known_items(items), weights=w)["score"]
        best = best_variant(weights=w)
        out.append({"direction": code, "name": name, "score": round(score, 2), "best_score": best["score"],
                    "gap": round(best["score"] - score, 2), "best_plan": best["plan"],
                    "best_changes": best["plan"] != official_best["plan"]})
    return out
