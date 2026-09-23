import json
import logging
import os
import re

from . import llm
from .data import load_data
from .optimizer import improve, top
from .scoring import baseline, evaluate
from .search import rank

log = logging.getLogger("akim.explain")

BORDER = 45
LEVER_D_AVG = 0.7
LEVER_MIN = 0.3

SYSTEM_PROMPT = """Ты — аналитик городского симулятора «Аким на 5 часов». Данные условные, это не реальная Астана.
Тебе дают JSON с готовым расчётом сценария. Напиши разбор для городского управленца.
Правила:
1. Используй только числа из JSON, в том же виде. Ничего не считай, не складывай и не придумывай.
2. Не упоминай реальных людей, политиков, партии и настоящий бюджет города.
3. Пиши по-русски, коротко и конкретно, без технических названий полей JSON. Говори «Score города» вместо
score, «прирост» вместо delta, «показатели ниже 40» вместо critical_now, «снятые критические показатели»
вместо resolved_critical. Называй районы, меры и показатели по понятным именам из JSON.
4. Ответ — строго JSON: {"strengths": [до 3 строк], "risks": [до 3 строк], "consequences": [до 3 строк],
"text": "итог в 2–3 предложениях"}."""


def fmt(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",").replace("-", "−")


def fmt_signed(x: float) -> str:
    return ("+" if x >= 0 else "") + fmt(x)


def _where(district) -> str:
    return f"в районе {district}" if district else "на весь город"


def facts(res: dict, imp: dict | None = None) -> dict:
    data = load_data()
    ind = {i["code"]: i["name"] for i in data["indicators"]}
    names = {m["id"]: m["name"] for m in data["measures"]}
    pop = {d["name"]: d["population_share"] for d in data["districts"]}

    borderline = []
    for d in res["districts"]:
        for code, value in d["values_after"].items():
            if 40 <= value < BORDER:
                borderline.append({"district": d["name"], "indicator": ind[code], "value": round(value, 2)})
    borderline.sort(key=lambda b: b["value"])

    min_name = res["min_district"]["name"]
    biggest = max(pop, key=pop.get)
    lever = [{"district": min_name, "score_per_point": round(LEVER_D_AVG * pop[min_name] + LEVER_MIN, 2)}]
    if biggest != min_name:
        lever.append({"district": biggest, "score_per_point": round(LEVER_D_AVG * pop[biggest], 2)})

    gaps_before = [d["d_before"] for d in res["districts"]]
    gaps_after = [d["d_after"] for d in res["districts"]]
    best_list = top(1)
    best = best_list[0] if best_list else None

    f = {
        "score": res["score"],
        "base_score": res["base_score"],
        "delta": res["delta"],
        "d_avg": res["d_avg"],
        "base_d_avg": res["base_d_avg"],
        "weakest_district": res["min_district"],
        "critical_now": [{"district": c["district"], "indicator": ind[c["indicator"]], "value": c["value"]}
                         for c in res["critical"]],
        "critical_before": baseline()["n_crit"],
        "resolved_critical": [{"district": c["district"], "indicator": ind[c["indicator"]],
                               "before": c["before"], "after": c["after"]} for c in res["resolved_critical"]],
        "new_critical": [{"district": c["district"], "indicator": ind[c["indicator"]],
                          "before": c["before"], "after": c["after"]} for c in res["new_critical"]],
        "borderline_40_45": borderline[:3],
        "contributions": sorted(
            [{"measure": c["measure"], "name": c["name"], "where": _where(c["district"]), "cost": c["cost"],
              "score_contribution": c["score_contribution"]} for c in res["contributions"]],
            key=lambda c: -c["score_contribution"]),
        "synergies": [{"measures": [names[p] for p in s["pair"]], "district": s["district"],
                       "indicator": ind[s["indicator"]], "bonus": s["bonus"]} for s in res["synergies"]],
        "slow_measures": [{"name": p["name"], "lag_quarters": p["lag"],
                           "realized_percent": round(p["realized_share"] * 100, 1)}
                          for p in res["plan"] if p["lag"] >= 3],
        "districts": [{"name": d["name"], "d_before": d["d_before"], "d_after": d["d_after"],
                       "d_delta": d["d_delta"]} for d in res["districts"]],
        "gap_best_worst_before": round(max(gaps_before) - min(gaps_before), 2),
        "gap_best_worst_after": round(max(gaps_after) - min(gaps_after), 2),
        "score_per_point_of_district": lever,
        "budget_used": res["budget_used"],
        "budget_left": res["budget_left"],
        "place_among_all": rank(res["plan"]),
        "best_possible_score": best["score"] if best else None,
        "gap_to_best": round(best["score"] - res["score"], 2) if best else None,
    }
    if imp and imp.get("better") and imp.get("best"):
        b = imp["best"]
        f["suggestion"] = {
            "replace": f"«{names[b['replace']['measure']]}» {_where(b['replace']['district'])}",
            "with": f"«{names[b['with']['measure']]}» {_where(b['with']['district'])}",
            "score": b["score"],
            "delta": b["delta"],
        }
    return f


def template(f: dict) -> dict:
    strengths, risks, consequences = [], [], []

    if f["resolved_critical"]:
        parts = ", ".join(f"{c['district']} — {c['indicator'].lower()} {fmt(c['before'])} → {fmt(c['after'])}"
                          for c in f["resolved_critical"])
        strengths.append(f"Сняты критические значения: {parts}. Штраф за показатели ниже 40 уменьшился.")
    for c in f["contributions"][:2]:
        if c["score_contribution"] > 0:
            strengths.append(f"«{c['name']}» {c['where']}: {fmt_signed(c['score_contribution'])} к Score.")
    for s in f["synergies"]:
        strengths.append(f"Сработала синергия «{s['measures'][0]}» и «{s['measures'][1]}»: "
                         f"{s['indicator'].lower()} в районе {s['district']} +{fmt(s['bonus'])}.")

    for c in f["new_critical"]:
        risks.append(f"Новая проблема: {c['district']} — {c['indicator'].lower()} {fmt(c['before'])} → "
                     f"{fmt(c['after'])}, ниже 40, штраф −1.")
    for c in f["critical_now"]:
        if not any(n["district"] == c["district"] and n["indicator"] == c["indicator"] for n in f["new_critical"]):
            risks.append(f"Осталось ниже 40: {c['district']} — {c['indicator'].lower()} {fmt(c['value'])}, штраф −1.")
    for b in f["borderline_40_45"][:2]:
        risks.append(f"На границе штрафа: {b['district']} — {b['indicator'].lower()} {fmt(b['value'])}.")
    weakest = f["contributions"][-1] if f["contributions"] else None
    if weakest and len(f["contributions"]) > 1:
        risks.append(f"Слабее всех по отдаче: «{weakest['name']}» {weakest['where']} — {weakest['cost']} единиц "
                     f"за {fmt_signed(weakest['score_contribution'])} к Score.")
    if f["budget_left"] >= 10:
        risks.append(f"Остаток бюджета {f['budget_left']} не работает: бонуса за экономию нет.")

    consequences.append(f"Score города: {fmt(f['base_score'])} → {fmt(f['score'])} ({fmt_signed(f['delta'])}).")
    w = f["weakest_district"]
    consequences.append(f"Самый слабый район теперь {w['name']} ({fmt(w['d'])}); разрыв лучшего и худшего района: "
                        f"{fmt(f['gap_best_worst_before'])} → {fmt(f['gap_best_worst_after'])}.")
    for s in f["slow_measures"][:1]:
        consequences.append(f"«{s['name']}»: лаг {s['lag_quarters']} кв., за 2 года сработает "
                            f"{fmt(s['realized_percent'])}% эффекта.")
    lever = f["score_per_point_of_district"]
    if len(lever) == 2:
        consequences.append(f"Балл района {lever[0]['district']} поднимает Score на "
                            f"{fmt(lever[0]['score_per_point'])}, балл района {lever[1]['district']} — на "
                            f"{fmt(lever[1]['score_per_point'])}: поднимать отстающего выгоднее.")

    text = f"Сценарий даёт {fmt(f['score'])} ({fmt_signed(f['delta'])} к базе)."
    place = f.get("place_among_all")
    if place:
        text += f" Место среди всех допустимых наборов: {place['rank']} из {place['total']:,}.".replace(",", " ")
    if f.get("suggestion"):
        s = f["suggestion"]
        text += f" Можно лучше: заменить {s['replace']} на {s['with']} — {fmt(s['score'])} ({fmt_signed(s['delta'])})."
    elif f.get("gap_to_best") is not None and f["gap_to_best"] <= 0:
        text += " Это лучший возможный набор."
    if f.get("gap_to_best") is not None and f["gap_to_best"] > 0:
        text += f" До лучшего возможного набора ({fmt(f['best_possible_score'])}) — {fmt(f['gap_to_best'])}."
    return {"strengths": strengths[:4], "risks": risks[:4], "consequences": consequences[:4], "text": text}


_CODES = re.compile(r"\b[MTESBCМТЕС]\d{1,2}\b")
_GROUPED = re.compile(r"(?<=\d)[\s  ](?=\d{3}\b)")
_NUMBER = re.compile(r"[-+−]?\d+(?:[.,]\d+)?")
_ALWAYS_OK = {float(n) for n in range(0, 11)} | {40.0, 45.0, 100.0, 30.0, 70.0}


def _collect(obj, out: set) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(abs(float(obj)))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, out)
    elif isinstance(obj, str):
        text = _GROUPED.sub("", _CODES.sub(" ", obj))
        for token in _NUMBER.findall(text):
            out.add(abs(float(token.replace(",", ".").replace("−", "-").lstrip("+-"))))


def unknown_numbers(payload: dict, f: dict) -> list[str]:
    allowed = set(_ALWAYS_OK)
    _collect(f, allowed)
    text = " ".join([*payload.get("strengths", []), *payload.get("risks", []),
                     *payload.get("consequences", []), payload.get("text", "")])
    text = _GROUPED.sub("", _CODES.sub(" ", text))
    bad = []
    for token in _NUMBER.findall(text):
        clean = token.replace(",", ".").replace("−", "-").lstrip("+-")
        value = float(clean)
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        if not any(abs(round(a, decimals) - value) < 1e-9 for a in allowed):
            bad.append(token)
    return bad


def _ask_model(f: dict) -> dict:
    reply = llm.complete(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": json.dumps(f, ensure_ascii=False)}],
        json_mode=True,
        model=os.getenv("OPENAI_EXPLAIN_MODEL", "gpt-5-mini"),
        max_completion_tokens=350,
        reasoning_effort="none",
    )
    payload = json.loads(reply.choices[0].message.content)
    return {
        "strengths": [str(s) for s in payload.get("strengths", [])][:4],
        "risks": [str(s) for s in payload.get("risks", [])][:4],
        "consequences": [str(s) for s in payload.get("consequences", [])][:4],
        "text": str(payload.get("text", "")),
    }


def explain(plan: list[dict]) -> dict:
    res = evaluate(plan)
    if not res["valid"]:
        reasons = [e["message"] for e in res["errors"]]
        return {"mode": "template", "strengths": [], "risks": reasons, "consequences": [],
                "text": "Набор недопустим, Score не считается: " + "; ".join(reasons), "suggestion": None}

    f = facts(res, improve(plan))
    base = {**template(f), "suggestion": f.get("suggestion")}
    if not llm.enabled():
        return {"mode": "template", **base}
    try:
        answer = _ask_model(f)
    except Exception as exc:
        log.warning("Модель не ответила, показываем шаблон: %s", exc)
        return {"mode": "template", "note": "Модель недоступна — показан шаблон.", **base}
    bad = unknown_numbers(answer, f)
    if bad:
        log.warning("Ответ модели отклонён: числа не из расчёта %s", bad)
        return {"mode": "template", "note": f"Ответ модели отклонён: числа {', '.join(bad)} не из расчёта.", **base}
    return {"mode": "llm", **answer, "suggestion": f.get("suggestion")}
