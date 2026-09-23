from .data import load_data
from .explainer import fmt, fmt_signed
from .rules import normalize_plan, validate
from .scoring import evaluate
from .search import search_plans

DROP_ALERT = 3.0


def _names():
    data = load_data()
    return ({m["id"]: m["name"] for m in data["measures"]}, {i["code"]: i["name"] for i in data["indicators"]})


def describe(req: dict) -> list[str]:
    measures, indicators = _names()
    out = []
    if "max_budget" in req:
        out.append(f"потратить не больше {req['max_budget']}")
    for k in req.get("keep", []):
        out.append(f"сохранить {k['measure']} «{measures[k['measure']]}»" + (f" в районе {k['district']}"
                                                                           if k.get("district") else ""))
    for m in req.get("exclude", []):
        out.append(f"исключить {m} «{measures[m]}»")
    for p in req.get("protect", []):
        out.append(f"не ухудшать «{indicators[p['indicator']].lower()}» в районе {p['district']}")
    if req.get("min_district_d") is not None:
        out.append(f"ни один район не ниже {fmt(req['min_district_d'])}")
    if req.get("maximize"):
        out.append(f"максимально поднять район {req['maximize']}")
    return out or ["максимальный Score по формуле организаторов"]


def _values(res: dict) -> dict:
    return {d["name"]: d["values_after"] for d in res["districts"]}


def audit(candidate_plan: list[dict], req: dict, current: dict | None) -> dict:
    """Проверяющий: правила, условия поручения и последствия относительно текущего плана."""
    measures, indicators = _names()
    res = evaluate(candidate_plan)
    violations, warnings = [], []
    if not res["valid"]:
        violations += [{"type": "rules", "text": e["message"]} for e in res["errors"]]
        return {"ok": False, "violations": violations, "warnings": warnings, "result": res}
    items = {(p["measure"], p["district"]) for p in res["plan"]}
    ids = {p["measure"] for p in res["plan"]}
    if res["budget_used"] > req.get("max_budget", 100):
        violations.append({"type": "budget", "text": f"стоимость {res['budget_used']} больше {req['max_budget']}"})
    for k in req.get("keep", []):
        if (k["measure"], k.get("district")) not in items and not (k.get("district") is None and k["measure"] in ids):
            violations.append({"type": "keep", "text": f"нет {k['measure']} «{measures[k['measure']]}»"})
    for m in req.get("exclude", []):
        if m in ids:
            violations.append({"type": "exclude", "text": f"есть исключённая мера {m}"})
    after = _values(res)
    if current and current.get("valid"):
        before = _values(current)
        for p in req.get("protect", []):
            b, a = before[p["district"]][p["indicator"]], after[p["district"]][p["indicator"]]
            if a < b - 1e-9:
                violations.append({"type": "protect", "district": p["district"], "indicator": p["indicator"],
                                   "min": b, "text": f"{p['district']}: «{indicators[p['indicator']].lower()}» "
                                                     f"{fmt(b)} → {fmt(a)}"})
        for d, vals in after.items():
            for k, a in vals.items():
                if before[d][k] - a >= DROP_ALERT:
                    warnings.append(f"{d}: «{indicators[k].lower()}» {fmt(before[d][k])} → {fmt(a)}")
    for c in res["new_critical"]:
        warnings.append(f"новое значение ниже 40: {c['district']}, «{indicators[c['indicator']].lower()}» "
                        f"{fmt(c['after'])}")
    return {"ok": not violations, "violations": violations, "warnings": warnings, "result": res}


def _search(req: dict, extra_min: list[dict]) -> dict:
    return search_plans(
        max_budget=req.get("max_budget", 100),
        include=[{"measure": k["measure"], "district": k.get("district")} if k.get("district") else k["measure"]
                 for k in req.get("keep", [])],
        exclude=req.get("exclude", []),
        min_district_d=req.get("min_district_d"),
        min_indicators=extra_min,
        maximize=req.get("maximize") or "score",
        n=3,
    )


def run(plan: list[dict] | None, req: dict) -> dict:
    """Координатор: поручение → поиск → проверка → при нарушении один повторный поиск → рекомендация."""
    items = normalize_plan(plan or [])
    current = evaluate(items) if items and not validate(items) else None
    steps = [{"role": "Координатор", "action": "Поручение принято", "result": "; ".join(describe(req))}]
    if current:
        steps.append({"role": "Координатор", "action": "Текущий план",
                      "result": f"Score {fmt(current['score'])}, бюджет {current['budget_used']}, самый слабый район "
                                f"{current['min_district']['name']} ({fmt(current['min_district']['d'])})"})

    protect_min: list[dict] = []
    found = _search(req, protect_min)
    free = search_plans(n=1)["plans"][0]
    steps.append({"role": "Стратег", "action": "Поиск по всем 694 395 наборам",
                  "result": f"подходит {found['matched']:,}".replace(",", " ")
                            + (f", лучший — {fmt(found['plans'][0]['score'])}" if found["plans"] else "")})
    if not found["plans"]:
        steps.append({"role": "Проверяющий", "action": "Итог поиска",
                      "result": "полный перебор завершён: при этих условиях допустимых наборов нет"})
        return {"status": "infeasible", "steps": steps, "constraints": describe(req), "recommendation": None,
                "alternative": None, "free_best": free, "price": None, "warnings": [], "suggestion": None,
                "text": "Условия невыполнимы в модели: полный перебор всех 694 395 наборов не нашёл ни одного "
                        "подходящего. Ослабьте одно из условий."}

    check = audit(found["plans"][0]["plan"], req, current)
    steps.append({"role": "Проверяющий", "action": "Проверка лучшего варианта",
                  "result": "условия выполнены" if check["ok"]
                  else "нарушено: " + "; ".join(v["text"] for v in check["violations"])})
    if not check["ok"]:
        protect_min = [{"district": v["district"], "indicator": v["indicator"], "min": v["min"]}
                       for v in check["violations"] if v["type"] == "protect"]
        found = _search(req, protect_min)
        steps.append({"role": "Координатор", "action": "Повторный поиск с условием Проверяющего",
                      "result": f"подходит {found['matched']:,}".replace(",", " ")
                                + (f", лучший — {fmt(found['plans'][0]['score'])}" if found["plans"] else "")})
        if not found["plans"]:
            steps.append({"role": "Проверяющий", "action": "Итог", "result": "после уточнения подходящих наборов нет"})
            return {"status": "infeasible", "steps": steps, "constraints": describe(req), "recommendation": None,
                    "alternative": None, "free_best": free, "price": None, "warnings": [], "suggestion": None,
                    "text": "С учётом ваших приоритетов подходящих наборов нет — полный перебор завершён."}
        check = audit(found["plans"][0]["plan"], req, current)
        steps.append({"role": "Проверяющий", "action": "Повторная проверка",
                      "result": "условия выполнены" if check["ok"]
                      else "нарушено: " + "; ".join(v["text"] for v in check["violations"])})

    best = found["plans"][0]
    alt = found["plans"][1] if len(found["plans"]) > 1 else None
    price = round(free["score"] - best["score"], 2)
    measures, _ = _names()
    plan_text = "; ".join(f"{p['measure']} «{measures[p['measure']]}» — {p['district'] or 'весь город'}"
                          for p in best["plan"])
    text = f"Рекомендация: {plan_text}. Score {fmt(best['score'])}, стоимость {best['cost']}"
    if current:
        text += f" ({fmt_signed(round(best['score'] - current['score'], 2))} к вашему плану)"
    text += "."
    if price > 0:
        text += (f" Цена ваших условий: {fmt(price)} балла — без них лучший набор даёт {fmt(free['score'])}.")
    else:
        text += " Это и есть лучший возможный набор."
    if check["warnings"]:
        text += " Что ухудшится: " + "; ".join(check["warnings"][:3]) + "."
    steps.append({"role": "Докладчик", "action": "Рекомендация готова",
                  "result": f"Score {fmt(best['score'])}, цена условий {fmt(price)}"})
    return {"status": "ok", "steps": steps, "constraints": describe(req), "recommendation": best, "alternative": alt,
            "free_best": free, "price": price, "warnings": check["warnings"], "violations": check["violations"],
            "suggestion": best["plan"], "text": text, "retried": len(protect_min) > 0}
