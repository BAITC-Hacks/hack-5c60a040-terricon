import json
import logging
import re

from . import llm
from . import mission
from .data import district_names, load_data
from .events import events, sensitivity, stress_test
from .nlu import districts_in, measures_in, parse_request
from .explainer import explain, fmt, fmt_signed, unknown_numbers
from .optimizer import improve
from .rules import normalize_plan, validate
from .scoring import evaluate
from .search import find_best, rank
from .tools import compare, district_report, frontier, what_if

log = logging.getLogger("akim.agent")
MAX_STEPS = 5

REFUSE_RULES = ("Формулу, бюджет и данные менять нельзя — они одинаковы для всех участников. "
                "Могу подобрать лучший набор в рамках правил.")
REFUSE_POLITICS = ("Это симулятор на условных данных: о реальных людях, политике и настоящем бюджете города "
                   "не сужу. Могу разобрать ваш сценарий.")
HELP = ("Я помощник городского управленца. Могу: объяснить сценарий («почему так?»), улучшить его («улучши»), "
        "подобрать набор под цель («лучший до 80 без ЛРТ», «чтобы ни один район не был ниже 55»), проверить "
        "замену («что если заменить M5 на M3 в Нуре»), рассказать о районе («что с Нурой?»), сравнить с лучшим "
        "(«сравни с лучшим»), назвать место сценария среди всех наборов. Решение применяете и утверждаете вы.")

_INJECTION = re.compile(
    r"забудь|игнорир|ignore|систем\w*\s+(промпт|инструкц|сообщ)|system prompt|покажи\s+(свой\s+)?(промпт|инструкц)|"
    r"твои\s+инструкц|developer mode|jailbreak|ты\s+теперь|притворись", re.I)
_CHEAT = re.compile(
    r"(постав|сдела|нарисуй|измени|подними|выстав|дай)\w*\s+(мне\s+)?(score|скор|балл|оценк)\w*\s*(на|=|до)?\s*\d|"
    r"(score|скор)\w*\s*(=|на)?\s*100\b|(увелич|измени|добав|подними)\w*\s+бюджет|бюджет\w*\s+(на\s+)?(1[0-9]{2}|[2-9]\d{2})|"
    r"(измени|поменяй|убери)\w*\s+(формул|вес|штраф|правил)", re.I)
_POLITICS = re.compile(
    r"парти[яи]|выбор(ы|ах|ов)\b|президент|депутат|маслихат|парламент|коррупц|оппозиц|митинг|санкци|религи|"
    r"(реальн|настоящ)\w*\s+(аким|бюджет|чиновник)|кто\s+виноват", re.I)

def check_input(message: str) -> str | None:
    if _INJECTION.search(message) or _CHEAT.search(message):
        return REFUSE_RULES
    if _POLITICS.search(message):
        return REFUSE_POLITICS
    return None


def _mission_answer(plan: list[dict], req: dict, mode: str = "rules") -> dict:
    r = mission.run(plan, req)
    tools = ["Разбор поручения", "Подбор под цель по всем наборам", "Проверяющий"]
    if r.get("retried"):
        tools.append("Повторный поиск")
    out = _answer(r["text"], "mission", tools, suggestion=r["suggestion"], mode=mode)
    out["mission"] = r
    return out


def _plan_text(plan: list[dict]) -> str:
    names = {m["id"]: m["name"] for m in load_data()["measures"]}
    return "; ".join(f"{p['measure']} «{names[p['measure']]}» — {p['district'] or 'весь город'}"
                     for p in normalize_plan(plan))


def _answer(reply: str, intent: str, tools: list[str], suggestion=None, mode: str = "rules", note=None) -> dict:
    out = {"reply": reply, "mode": mode, "intent": intent, "tools_used": tools, "suggestion": suggestion}
    if note:
        out["note"] = note
    return out


def _rules_chat(message: str, plan: list[dict]) -> dict:
    low = message.lower()
    items = normalize_plan(plan or [])
    valid = bool(items) and not validate(items)
    measures = measures_in(message)
    districts = districts_in(message)

    if re.search(r"что\s+(будет\s+)?если|а\s+если|замени|поменя", low) and measures:
        remove = measures[0] if len(measures) > 1 else None
        add_id = measures[-1]
        scope = next(m["scope"] for m in load_data()["measures"] if m["id"] == add_id)
        add = {"measure": add_id, "district": (districts[0] if districts else None) if scope == "district" else None}
        if scope == "district" and not add["district"]:
            return _answer(f"Для меры {add_id} нужен район: например, «что если заменить {remove or 'M5'} на "
                           f"{add_id} в Нуре».", "what_if", [])
        w = what_if(items, remove=remove, add=add)
        after = w["after"]
        if not after["valid"]:
            reasons = "; ".join(e["message"] for e in after["errors"])
            return _answer(f"Такой набор недопустим: {reasons}.", "what_if", ["«Что если»", "Проверка правил"])
        base = f"{fmt(w['before'])} → " if w["before"] is not None else ""
        delta = f" ({fmt_signed(w['delta'])})" if w["delta"] is not None else ""
        return _answer(f"Получится Score {base}{fmt(after['score'])}{delta}. Самый слабый район — "
                       f"{after['min_district']['name']} ({fmt(after['min_district']['d'])}), показателей ниже 40: "
                       f"{after['n_crit']}. Применить — кнопкой на экране.",
                       "what_if", ["«Что если»", "Расчёт Score"], suggestion=w["new_plan"])

    req = parse_request(message, items)
    wants_best = re.search(r"лучш|оптимал|подбер|подобр|макс", low)
    if wants_best and "max_budget" not in req:
        budget = re.search(r"(?:до|не\s+больше|не\s+дороже|в\s+пределах|за)\s+(\d{2,3})\b", low)
        if budget and 10 <= int(budget.group(1)) <= 100:
            req["max_budget"] = int(budget.group(1))
    if req or (wants_best and not valid) or re.search(r"подбер|подобр", low):
        return _mission_answer(items, req)

    if re.search(r"улучш|лучше|подним|повыс|оптимиз", low):
        if not valid:
            b = find_best(n=1)[0]
            return _answer(f"Ваш набор пока недопустим. Лучший возможный: {_plan_text(b['plan'])} — Score "
                           f"{fmt(b['score'])}.", "improve", ["Подбор под цель по всем наборам"], suggestion=b["plan"])
        imp = improve(items)
        if not imp.get("better"):
            return _answer(f"Замена одной меры Score не поднимет: {fmt(imp['current_score'])} — лучше не найти "
                           "одной заменой.", "improve", ["Улучшить на одну меру"])
        b = imp["best"]
        return _answer(f"Замените {b['replace']['measure']} ({b['replace']['district'] or 'весь город'}) на "
                       f"{b['with']['measure']} ({b['with']['district'] or 'весь город'}): Score "
                       f"{fmt(imp['current_score'])} → {fmt(b['score'])} ({fmt_signed(b['delta'])}). "
                       "Применить — кнопкой на экране.",
                       "improve", ["Улучшить на одну меру"], suggestion=b["plan"])

    if districts and re.search(r"что\s+с|как\s+(там|дела)|паспорт|болит|проблем|помочь|поднять|слаб|район", low):
        r = district_report(districts[0], items if valid else None)
        weak = ", ".join(f"{w['name'].lower()} {fmt(w['value'])}" for w in r["weak"][:3])
        cure = "; ".join(f"{m['measure']} «{m['name']}» ({fmt_signed(m['score_gain'])} к Score)"
                         for m in r["best_measures"][:3])
        return _answer(f"{r['district']}: балл {fmt(r['d'])}, {r['place_from_bottom']}-е место с конца. "
                       f"Слабые места: {weak}. Сильнее всего помогут: {cure}.",
                       "district_report", ["Паспорт района"])

    event = next((e for e in events() if re.search(
        {"smog": r"смог|задымл", "heating": r"теплосет|авари\w*\s+(на\s+)?тепл|без\s+отоплен",
         "school_boom": r"школьник|рост\w*\s+(числа\s+)?дет", "flood": r"паводок|подтоплен|наводнен"}[e["id"]], low)),
                 None)
    if event and valid:
        r = stress_test(items, event["id"])
        return _answer(r["text"], "stress_test", ["Городские события"],
                       suggestion=r["advice"]["plan"] if r["advice"] else None)

    if re.search(r"устойчив|приоритет|если\s+\w+\s+важнее|веса", low) and valid:
        rows = sensitivity(items)
        changed = [r["name"] for r in rows if r["best_changes"]]
        text = "Если одно направление станет важнее на 20%: " + "; ".join(
            f"{r['name'].lower()} — ваш сценарий {fmt(r['score'])}, лучший {fmt(r['best_score'])}" for r in rows) + "."
        text += (f" Лучший набор меняется при приоритете: {', '.join(c.lower() for c in changed)}." if changed
                 else " Лучший набор от приоритетов не зависит.")
        return _answer(text, "sensitivity", ["Устойчивость к приоритетам"])

    if re.search(r"сравн", low):
        if not valid:
            return _answer("Сначала соберите допустимый набор из 5 решений — тогда сравню.", "compare", [])
        best = find_best(n=1)[0]
        c = compare(items, best["plan"])
        diff = ", ".join(f"{d['name']} {fmt_signed(d['diff'])}" for d in c["districts"])
        return _answer(f"Лучший набор даёт {fmt(best['score'])} — на {fmt(c['score_diff'])} больше вашего. "
                       f"По районам: {diff}.", "compare", ["Сравнение сценариев", "Подбор под цель по всем наборам"],
                       suggestion=best["plan"])

    if re.search(r"мест|рейтинг|насколько\s+хорош|позици", low) and valid:
        p = rank(items)
        return _answer(f"Ваш сценарий — {p['rank']}-й из {p['total']:,}".replace(",", " ")
                       + f" допустимых наборов; лучший даёт {fmt(p['best_score'])}.", "rank", ["Место сценария"])

    if re.search(r"бюджет|осталось|потрач|сколько\s+сто", low):
        res = evaluate(items)
        return _answer(f"Потрачено {res['budget_used']} из {res['budget']}, остаток {res['budget_left']}. "
                       "Остаток не сгорает, но и бонуса не даёт.", "budget", ["Проверка правил"])

    if re.search(r"кривая|сколько\s+(нужно|надо)\s+потрат|экономи", low):
        points = frontier()
        good = [p for p in points if p["score"] >= points[-1]["score"] - 0.5]
        cheapest = min(good, key=lambda p: p["cost"]) if good else points[-1]
        return _answer(f"Лучший Score 57,24 стоит 98, но уже за {cheapest['cost']} можно получить "
                       f"{fmt(cheapest['score'])}.", "frontier", ["Кривая «бюджет → Score»"],
                       suggestion=cheapest["plan"])

    if re.search(r"почему|объясн|разбор|риск|сильн|компромисс|последств|итог", low) or valid:
        if not valid:
            return _answer(HELP, "help", [])
        e = explain(items)
        parts = [e["text"]] + e["risks"][:2]
        return _answer(" ".join(parts), "explain", ["Разбор компромиссов"], suggestion=e.get("suggestion") and
                       improve(items)["best"]["plan"])

    return _answer(HELP, "help", [])


TOOL_TITLES = {
    "evaluate_plan": "Расчёт Score", "explain_plan": "Разбор компромиссов", "improve_plan": "Улучшить на одну меру",
    "find_best": "Подбор под цель по всем наборам", "plan_rank": "Место сценария", "district_report": "Паспорт района",
    "compare_plans": "Сравнение сценариев", "what_if": "«Что если»", "budget_frontier": "Кривая «бюджет → Score»",
    "run_mission": "Поручение: поиск → Проверяющий → повторный поиск",
    "stress_test": "Городские события", "sensitivity": "Устойчивость к приоритетам",
}
_PLAN_SCHEMA = {"type": "array", "items": {"type": "object", "properties": {
    "measure": {"type": "string", "description": "M1…M14"},
    "district": {"type": ["string", "null"], "description": "район для районной меры, null для городской"}},
    "required": ["measure", "district"]}}


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": properties,
                                                            "required": required}}}


TOOLS = [
    _tool("evaluate_plan", "Проверить правила и посчитать Score набора из 5 решений.", {"plan": _PLAN_SCHEMA}, ["plan"]),
    _tool("explain_plan", "Сильные стороны, риски и последствия сценария.", {"plan": _PLAN_SCHEMA}, ["plan"]),
    _tool("improve_plan", "Лучшая замена одной меры в допустимом наборе.", {"plan": _PLAN_SCHEMA}, ["plan"]),
    _tool("find_best", "Лучшие наборы среди всех 694 395 допустимых с условиями.", {
        "max_budget": {"type": "number"}, "include": {"type": "array", "items": {"type": "string"}},
        "exclude": {"type": "array", "items": {"type": "string"}}, "min_district_d": {"type": ["number", "null"]},
        "n": {"type": "integer"}}, []),
    _tool("plan_rank", "Место набора среди всех допустимых.", {"plan": _PLAN_SCHEMA}, ["plan"]),
    _tool("district_report", "Слабые показатели района и меры, которые поднимут его сильнее всего.", {
        "district": {"type": "string", "enum": list(district_names())}, "plan": _PLAN_SCHEMA}, ["district"]),
    _tool("compare_plans", "Сравнить два набора по Score и районам.", {"plan_a": _PLAN_SCHEMA, "plan_b": _PLAN_SCHEMA},
          ["plan_a", "plan_b"]),
    _tool("what_if", "Пересчитать набор после удаления и/или добавления меры.", {
        "plan": _PLAN_SCHEMA, "remove": {"type": ["string", "null"]},
        "add": {"type": ["object", "null"], "properties": {"measure": {"type": "string"},
                                                           "district": {"type": ["string", "null"]}}}}, ["plan"]),
    _tool("budget_frontier", "Лучший Score при каждой сумме затрат.", {}, []),
    _tool("run_mission",
          "Выполнить поручение управленца: найти лучший набор при его условиях по всем 694 395 наборам, проверить "
          "последствия относительно текущего плана, при нарушении приоритета повторить поиск и назвать цену условий. "
          "Используй для любых запросов с ограничениями и приоритетами.", {
              "max_budget": {"type": "number", "description": "не тратить больше; по умолчанию 100"},
              "keep": {"type": "array", "description": "меры, которые надо сохранить",
                       "items": {"type": "object", "properties": {"measure": {"type": "string"},
                                                                  "district": {"type": ["string", "null"]}}}},
              "exclude": {"type": "array", "items": {"type": "string"}, "description": "запрещённые меры M1…M14"},
              "protect": {"type": "array", "description": "показатели района, которые нельзя ухудшать",
                          "items": {"type": "object", "properties": {
                              "district": {"type": "string", "enum": list(district_names())},
                              "indicator": {"type": "string", "description": "T1, T2, E1, E2, S1, S2, B1, B2, C1, C2"}}}},
              "min_district_d": {"type": ["number", "null"], "description": "ни один район не ниже"},
              "maximize": {"type": "string", "description": "score или название района, который поднять"},
          }, []),
    _tool("stress_test", "Пересчитать сценарий при городском событии и дать совет.", {
        "plan": _PLAN_SCHEMA, "event_id": {"type": "string", "enum": ["smog", "heating", "school_boom", "flood"]}},
          ["plan", "event_id"]),
    _tool("sensitivity", "Как меняется Score сценария и лучший набор, если одно направление важнее на 20%.",
          {"plan": _PLAN_SCHEMA}, ["plan"]),
]

SYSTEM_PROMPT = """Ты — помощник городского управленца в симуляторе «Аким на 5 часов» (условные данные, не реальная Астана).
Бюджет 100, ровно 5 решений из 14 мер, 5 районов. Считают только инструменты — вызывай их, сам ничего не считай.
Используй только числа из ответов инструментов и из сообщения пользователя. Не придумывай чисел.
Если пользователь задаёт условие или приоритет («не ухудшай», «сохрани», «исключи», «не больше», «не ниже»),
обязательно используй run_mission. improve_plan не умеет соблюдать такие условия.
Ты не применяешь и не утверждаешь сценарий: предлагаешь, решает человек кнопками на экране.
Не обсуждай реальных людей, политику и настоящий бюджет города. Отвечай по-русски, коротко, 2–5 предложений."""


def _compact(name: str, result):
    if name in ("evaluate_plan", "what_if"):
        r = result["after"] if name == "what_if" else result
        keep = {k: r[k] for k in ("valid", "score", "delta", "budget_used", "budget_left", "min_district", "n_crit",
                                  "critical", "contributions", "synergies")}
        keep["errors"] = [e["message"] for e in r["errors"]]
        if name == "what_if":
            return {"before": result["before"], "delta": result["delta"], "after": keep, "new_plan": result["new_plan"]}
        return keep
    if name == "compare_plans":
        return {k: result[k] for k in ("score_diff", "districts", "only_in_a", "only_in_b")} | {
            "score_a": result["a"]["score"], "score_b": result["b"]["score"]}
    if name == "budget_frontier":
        return [{"cost": p["cost"], "score": p["score"]} for p in result]
    if name == "run_mission":
        rec = result["recommendation"]
        return {"status": result["status"], "steps": result["steps"], "price": result["price"],
                "warnings": result["warnings"], "free_best_score": result["free_best"]["score"],
                "recommendation": rec and {"score": rec["score"], "cost": rec["cost"], "plan": rec["plan"]},
                "summary": result["text"]}
    return result


def _run_tool(name: str, args: dict, plan: list[dict] | None = None):
    if name == "run_mission":
        req = {k: v for k, v in args.items() if v not in (None, [], "", "score")}
        return mission.run(plan or [], req)
    if name == "evaluate_plan":
        return evaluate(args["plan"])
    if name == "explain_plan":
        e = explain(args["plan"])
        return {k: e[k] for k in ("strengths", "risks", "consequences", "text")}
    if name == "improve_plan":
        return improve(args["plan"])
    if name == "find_best":
        return find_best(max_budget=args.get("max_budget") or 100, include=args.get("include") or (),
                         exclude=args.get("exclude") or (), min_district_d=args.get("min_district_d"),
                         n=min(int(args.get("n") or 3), 5))
    if name == "plan_rank":
        return rank(args["plan"])
    if name == "district_report":
        return district_report(args["district"], args.get("plan"))
    if name == "compare_plans":
        return compare(args["plan_a"], args["plan_b"])
    if name == "what_if":
        return what_if(args["plan"], remove=args.get("remove"), add=args.get("add"))
    if name == "budget_frontier":
        return frontier()
    if name == "stress_test":
        return stress_test(args["plan"], args["event_id"])
    if name == "sensitivity":
        return sensitivity(args["plan"])
    raise ValueError(f"неизвестный инструмент {name}")


def _suggestion_from(name: str, result):
    if name == "improve_plan" and result.get("better"):
        return result["best"]["plan"]
    if name == "find_best" and result:
        return result[0]["plan"]
    if name == "what_if" and result["after"]["valid"]:
        return result["new_plan"]
    if name == "run_mission":
        return result["suggestion"]
    if name == "stress_test" and result.get("advice"):
        return result["advice"]["plan"]
    return None


def _llm_chat(message: str, plan: list[dict], history: list[dict]) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-8:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])})
    request = parse_request(message, plan or [])
    routing = ("\n\nВ запросе обнаружены условия. Обязательно вызови run_mission с этими условиями: "
               f"{json.dumps(request, ensure_ascii=False)}" if request else "")
    messages.append({"role": "user", "content": f"{message}{routing}\n\nТекущий набор пользователя: "
                                                f"{json.dumps(normalize_plan(plan or []), ensure_ascii=False)}"})
    used, facts, suggestion, last_mission = [], [], None, None
    user_numbers = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", message)]
    for _ in range(MAX_STEPS):
        reply = llm.complete(messages, tools=TOOLS)
        msg = reply.choices[0].message
        if not msg.tool_calls:
            text = (msg.content or "").strip()
            bad = unknown_numbers({"text": text}, {"tools": facts, "message": user_numbers})
            if bad:
                log.warning("Ответ агента отклонён проверкой чисел: %s", bad)
                fallback = _rules_chat(message, plan)
                fallback["note"] = f"Ответ модели отклонён: числа {', '.join(bad)} не из расчёта."
                return fallback
            out = _answer(text, "llm", [TOOL_TITLES.get(u, u) for u in used], suggestion, mode="llm")
            if last_mission:
                out["mission"] = last_mission
            return out
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": c.id, "type": "function",
                                         "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                        for c in msg.tool_calls]})
        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
                if name == "run_mission" and request:
                    args = request
                result = _run_tool(name, args, plan)
                suggestion = _suggestion_from(name, result) or suggestion
                if name == "run_mission":
                    last_mission = result
                content = _compact(name, result)
            except Exception as exc:
                content = {"error": str(exc)}
            used.append(name)
            facts.append(content)
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(content, ensure_ascii=False, default=str)})
    fallback = _rules_chat(message, plan)
    fallback["note"] = "Агент не уложился в 5 шагов — показан ответ по правилам."
    return fallback


def chat(message: str, plan: list[dict] | None = None, history: list[dict] | None = None) -> dict:
    text = (message or "").strip()
    if not text:
        return _answer(HELP, "help", [])
    refusal = check_input(text)
    if refusal:
        return _answer(refusal, "refused", ["Проверка на входе"])
    if llm.enabled():
        try:
            return _llm_chat(text, plan or [], history or [])
        except Exception as exc:
            log.warning("Модель не ответила, отвечаю по правилам: %s", exc)
            fallback = _rules_chat(text, plan or [])
            fallback["note"] = "Модель недоступна — ответ по правилам."
            return fallback
    return _rules_chat(text, plan or [])
