from datetime import datetime

from .data import load_data
from .explainer import explain, fmt, fmt_signed
from .scoring import evaluate
from .search import rank


def brief(plan: list[dict]) -> str:
    res = evaluate(plan)
    data = load_data()
    ind = [i["code"] for i in data["indicators"]]
    lines = [f"# Паспорт сценария «Аким на 5 часов»", "",
             f"Сформирован {datetime.now().strftime('%d.%m.%Y %H:%M')}. Данные условные (задача Astana Innovations, "
             "HackAlem AI). Решение утверждает человек — агент готовит и объясняет.", ""]
    if not res["valid"]:
        lines += ["**Набор недопустим, Score не считается:**", ""]
        lines += [f"- {e['message']}" for e in res["errors"]]
        return "\n".join(lines) + "\n"

    place = rank(plan)
    lines += ["## Итог", "",
              f"- **Astana Quality of Life Score: {fmt(res['score'])}** ({fmt_signed(res['delta'])} к базе "
              f"{fmt(res['base_score'])})",
              f"- Место среди всех допустимых наборов: {place['rank']} из {place['total']:,}".replace(",", " ")
              + f" (лучший — {fmt(place['best_score'])})",
              f"- Самый слабый район: {res['min_district']['name']} ({fmt(res['min_district']['d'])})",
              f"- Показателей ниже 40: {res['n_crit']}",
              f"- Бюджет: {res['budget_used']} из {res['budget']}", "",
              "## Решения", "", "| Мера | Где | Стоимость | Лаг, кв. | Вклад в Score |", "|---|---|---|---|---|"]
    contrib = {(c["measure"], c["district"]): c["score_contribution"] for c in res["contributions"]}
    for p in res["plan"]:
        lines.append(f"| {p['measure']} · {p['name']} | {p['district'] or 'весь город'} | {p['cost']} | {p['lag']} | "
                     f"{fmt_signed(contrib[(p['measure'], p['district'])])} |")
    lines += ["", "## Районы через 2 года", "", "| Район | D до | D после | " + " | ".join(ind) + " |",
              "|---|---|---|" + "---|" * len(ind)]
    for d in res["districts"]:
        cells = " | ".join(("**" + fmt(d["values_after"][k]) + "**") if d["values_after"][k] < 40
                           else fmt(d["values_after"][k]) for k in ind)
        lines.append(f"| {d['name']} | {fmt(d['d_before'])} | {fmt(d['d_after'])} | {cells} |")

    note = explain(plan)
    lines += ["", "## Разбор агента", "", "**Сильные стороны**", ""] + [f"- {s}" for s in note["strengths"]]
    lines += ["", "**Риски**", ""] + [f"- {s}" for s in note["risks"]]
    lines += ["", "**Последствия**", ""] + [f"- {s}" for s in note["consequences"]]
    lines += ["", note["text"], "",
              f"_Текст разбора: {'модель OpenAI, числа сверены с расчётом' if note['mode'] == 'llm' else 'шаблон по расчёту'}._"]
    return "\n".join(lines) + "\n"
