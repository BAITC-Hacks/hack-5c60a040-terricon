"""Экран «Аким на 5 часов»: одна история сверху вниз — «понять за 5 секунд».

Экран ничего не считает: всё, что на нём видно, — ответы движка akim.
"""

import html
import re

import streamlit as st
import streamlit.components.v1 as components

import akim
from city_view import ICONS, city_html

DIRECTION_ICONS = {"transport": "🚌", "ecology": "🌳", "social": "🏫", "safety": "🛡️", "services": "🏛️"}

EXAMPLE_PLAN = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]
STATE_BY_PLAN = ("improvement", "mission_result", "stress_result")

st.set_page_config(page_title="Аким на 5 часов", page_icon="🏙️", layout="wide")
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1240px;}
.akim-head {background: #00ABC2; border-bottom: 6px solid #FEC50C; border-radius: .8rem; padding: 1.1rem 1.4rem;
  color: #06303A; margin-bottom: .9rem;}
.akim-head h1 {font-size: 2rem; margin: 0; padding: 0; color: #06303A;}
.akim-head p {margin: .3rem 0 0; font-size: 1.05rem; color: #06303A;}
.akim-lead {font-size: 1.25rem; line-height: 1.5; background: #FFFFFF; border: 1px solid #B9DDE5;
  border-left: 6px solid #007E99; border-radius: 0; padding: .9rem 1.1rem; margin: .2rem 0 .8rem;}
.akim-lead.bad {border-left-color: #C62828;}
.akim-cards {display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .7rem; margin-bottom: .6rem;}
.akim-card {background: #FFFFFF; border: 1px solid #B9DDE5; border-radius: .7rem; padding: .7rem .9rem;}
.akim-card .t {font-size: .85rem; color: #3D5A6C;}
.akim-card .v {font-size: 1.9rem; font-weight: 700; color: #0B2545; line-height: 1.2;}
.akim-card .s {font-size: .85rem; color: #3D5A6C;}
.up {color: #1B7F4B; font-weight: 600;} .down {color: #C62828; font-weight: 600;}
.akim-step {font-size: .95rem; color: #3D5A6C; margin: -.4rem 0 .6rem;}
.akim-row {display: flex; justify-content: space-between; align-items: center; gap: .6rem; background: #FFFFFF;
  border: 1px solid #D5E9EE; border-radius: .5rem; padding: .45rem .7rem; margin-bottom: .35rem;}
.akim-row b {color: #0B2545;}
.chip {border-radius: 1rem; padding: .1rem .55rem; font-size: .85rem; font-weight: 600; white-space: nowrap;}
.chip.good {background: #E6F4EC; color: #1B5E3A;} .chip.bad {background: #FDECEA; color: #8E1C1C;}
.chip.warn {background: #FFF4D6; color: #7A5200;} .chip.same {background: #EEF2F4; color: #3D5A6C;}
.bar {height: .55rem; background: #00ABC2; border-radius: .3rem;}
.akim-table {overflow-x: auto;}
.akim-table table {border-collapse: collapse; width: 100%; font-size: .88rem; background: #FFFFFF; color: #0B2545;}
.akim-table th, .akim-table td {border: 1px solid #D5E9EE; padding: .4rem .5rem; text-align: center; color: #0B2545;}
.akim-table thead th {background: #E3F4F7;}
.akim-table tbody th {text-align: left; font-weight: 600;}
div[data-baseweb="tab-list"] button p {font-size: 1.05rem; font-weight: 600;}
div[data-baseweb="tab-list"] {gap: 1.2rem;}
</style>
""",
    unsafe_allow_html=True,
)


def fmt(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def fmt_short(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def signed(value: float) -> str:
    return ("+" if value >= 0 else "−") + fmt(abs(value))


def quarters(count: int) -> str:
    if count == 0:
        return "работает сразу"
    if count % 10 == 1 and count % 100 != 11:
        word = "квартал"
    elif 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        word = "квартала"
    else:
        word = "кварталов"
    return f"заработает через {count} {word}"


def esc(text) -> str:
    return html.escape(str(text))


PLAIN_WORDS = [
    ("Сняты критические значения", "Решены острые проблемы"), ("критические значения", "острые проблемы"),
    ("критическое значение", "острая проблема"), ("На границе штрафа", "На грани острой проблемы"),
    ("Сработала синергия", "Решения усилили друг друга:"), ("синергия", "усиление решений"),
    ("Score города", "Индекс города"), ("к Score", "к индексу"), ("Score", "индекс"),
]


def plain(text: str) -> str:
    """Тексты движка — простыми словами: без «Score», «лаг», «критические значения»."""
    text = re.sub(r"лаг (\d+) кв\.", lambda match: quarters(int(match.group(1))), str(text))
    for old, new in PLAIN_WORDS:
        text = text.replace(old, new)
    return text


data = akim.load_data()
base = akim.baseline()
measures = data["measures"]
measure_by_id = {measure["id"]: measure for measure in measures}
measure_ids = [measure["id"] for measure in measures]
indicator_name = {indicator["code"]: indicator["name"] for indicator in data["indicators"]}
indicator_codes = [indicator["code"] for indicator in data["indicators"]]
direction_name = {direction["code"]: direction["name"] for direction in data["directions"]}
district_names = [district["name"] for district in data["districts"]]
weakest_now = min(base["districts"], key=lambda district: district["d"])["name"]


def measure_title(measure_id: str) -> str:
    measure = measure_by_id[measure_id]
    where = " · весь город" if measure["scope"] == "city" else ""
    return f"{measure['cost']} · {DIRECTION_ICONS[measure['direction']]} {measure['name']}{where}"


def measure_details(measure_id: str) -> str:
    measure = measure_by_id[measure_id]
    effects = ", ".join(f"{ICONS[code]} {indicator_name[code].lower()} +{value:g}"
                        for code, value in measure["effects"].items())
    where = " · для всего города" if measure["scope"] == "city" else ""
    return (f"**Цена {measure['cost']}** · {direction_name[measure['direction']]} · {effects} · "
            f"{quarters(measure['lag'])}{where}")


def place(item: dict) -> str:
    return item.get("district") or "весь город"


def plan_words(plan: list[dict]) -> str:
    return "; ".join(f"{measure_by_id[item['measure']]['name']} — {place(item)}" for item in plan)


def swap_words(old: dict, new: dict) -> str:
    return (
        f"заменить «{measure_by_id[old['measure']]['name']}» ({place(old)}) "
        f"на «{measure_by_id[new['measure']]['name']}» ({place(new)})"
    )


def apply_plan(plan: list[dict]) -> None:
    """Обработчик кнопок «Применить» и «Взять»: страница перезапустится сама."""
    st.session_state["plan"] = [dict(item) for item in plan]
    for index, item in enumerate(plan):
        st.session_state[f"measure_{index}"] = item["measure"]
        if item.get("district"):
            st.session_state[f"district_{index}"] = item["district"]
        else:
            st.session_state.pop(f"district_{index}", None)
    for key in STATE_BY_PLAN:
        st.session_state.pop(key, None)


def plan_key(plan: list[dict]) -> tuple:
    return tuple((item["measure"], item.get("district")) for item in plan)


if "plan" not in st.session_state:
    st.session_state["plan"] = [dict(item) for item in EXAMPLE_PLAN]
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
for index, item in enumerate(st.session_state["plan"]):
    st.session_state.setdefault(f"measure_{index}", item["measure"])
    if item.get("district"):
        st.session_state.setdefault(f"district_{index}", item["district"])

# ---------- Шапка и суть ----------
st.markdown(
    '<div class="akim-head"><h1>Аким на 5 часов</h1>'
    "<p>Вы — аким Астаны: 100 единиц бюджета и 5 решений. Задача — поднять индекс качества жизни города "
    "и не бросить отстающие районы.</p></div>",
    unsafe_allow_html=True,
)
with st.expander("Как это работает и откуда цифры — 30 секунд"):
    st.markdown(
        "1. **Город сейчас.** Пять районов Астаны, у каждого 10 показателей от 0 до 100: дороги, транспорт, "
        "зелень, воздух, школы, поликлиники, безопасность, ЖКХ, обращения жителей. Данные условные — их вместе "
        "с задачей дала компания Astana Innovations, заказчик этой задачи на хакатоне.\n"
        "2. **Вы выбираете 5 решений** из 14 мер и район для каждой. Правила: бюджет не больше 100, одна мера — "
        "один раз, не больше двух мер одного направления, некоторые меры несовместимы.\n"
        "3. **Программа считает индекс** по формуле из условий задачи. Балл района — это его 10 показателей "
        "с весами. Индекс города: 70% — средний балл районов с учётом того, сколько в них живёт людей, "
        "30% — балл самого слабого района, минус 1 за каждую острую проблему (показатель ниже 40). Поэтому "
        "выгоднее подтягивать отстающих. Мера работает не сразу: если заработает через 3 квартала, за 2 года "
        "даст 5/8 эффекта.\n"
        "4. **ИИ-агент объясняет и советует**: что получилось, где риск, как улучшить. Считает всегда программа — "
        "каждое число в словах агента сверяется с расчётом.\n"
        "5. **Решаете вы**: применить совет, проверить сценарий на прочность, утвердить — только кнопкой."
    )

# ---------- «Главное» — место над вкладками; заполняется ниже, когда посчитан выбор ----------
lead = st.container()

tab_plan, tab_agent, tab_check, tab_decide = st.tabs(
    ["1 · Ваши решения и результат", "2 · Совет ИИ-агента", "3 · Проверка на прочность", "4 · Утвердить и рейтинг"]
)

with tab_plan:
    choose_col, result_col = st.columns([1, 1.15], gap="large")
    with choose_col:
        st.subheader("Ваши 5 решений")
        st.markdown('<div class="akim-step">В каждом из 5 полей — одна мера. Число в начале строки — её цена из 100. <b>Районная мера</b> работает в районе, который вы выберете; <b>городская</b> (пометка «весь город») — сразу во всех районах, поэтому района у неё нет. Не больше двух мер одного направления. Результат справа пересчитывается сразу.</div>',
                    unsafe_allow_html=True)
        selected = []
        for index in range(5):
            with st.container(border=True):
                measure_id = st.selectbox(
                    f"Решение {index + 1} из 5: цена · мера", measure_ids, format_func=measure_title,
                    key=f"measure_{index}"
                )
                if measure_by_id[measure_id]["scope"] == "district":
                    st.session_state.setdefault(f"district_{index}", weakest_now)
                    district = st.selectbox("Где: район", district_names, key=f"district_{index}")
                else:
                    district = None
                    st.markdown("**Где:** весь город — мера работает во всех районах сразу")
                st.caption(measure_details(measure_id))
            selected.append({"measure": measure_id, "district": district})
        st.session_state["plan"] = selected

plan = st.session_state["plan"]
result = akim.evaluate(plan)
districts_after = {district["name"]: district for district in result["districts"]}

with tab_plan:
    with choose_col:
        used, budget = result["budget_used"], result["budget"]
        st.progress(min(used, budget) / budget, text=f"Бюджет: потрачено {used} из {budget}, "
                    + (f"осталось {budget - used}" if used <= budget else f"перерасход {used - budget}"))
        if result["valid"]:
            st.success("Все правила соблюдены")
        else:
            for error in result["errors"]:
                st.error(error["message"])
        reset_col, best_col = st.columns(2)
        reset_col.button("Вернуть пример организаторов", key="reset_example", on_click=apply_plan,
                         args=(EXAMPLE_PLAN,), use_container_width=True)
        best = akim.top(1)[0]
        best_col.button(f"Взять лучший вариант ({fmt(best['score'])})", key="take_best", on_click=apply_plan,
                        args=(best["plan"],), use_container_width=True)

with lead:
    if result["valid"]:
        weakest = result["min_district"]
        verb = "поднимает" if result["delta"] > 0 else ("снижает" if result["delta"] < 0 else "не меняет")
        crit = (
            f"Острых проблем не осталось (было {base['n_crit']})."
            if result["n_crit"] == 0
            else f"Острых проблем: {result['n_crit']} (было {base['n_crit']})."
        )
        st.markdown(
            f'<div class="akim-lead"><b>Главное:</b> ваш сценарий {verb} индекс качества жизни Астаны '
            f"с {fmt(result['base_score'])} до <b>{fmt(result['score'])}</b> ({signed(result['delta'])}). "
            f"Отстающий район — {esc(weakest['name'])}: {fmt(weakest['d'])} из 100. {crit} "
            f"Потрачено {used} из {budget}.</div>",
            unsafe_allow_html=True,
        )
        weak_row = districts_after[weakest["name"]]
        delta_class = "up" if result["delta"] > 0 else ("down" if result["delta"] < 0 else "")
        cards = [
            ("Индекс качества жизни (Astana Quality of Life Score)", fmt(result["score"]),
             f"было {fmt(result['base_score'])} · <span class='{delta_class}'>{signed(result['delta'])}</span>"),
            ("Отстающий район", esc(weakest["name"]),
             f"{fmt(weak_row['d_before'])} → {fmt(weak_row['d_after'])} из 100"),
            ("Острые проблемы — показатели ниже 40", str(result["n_crit"]), f"было {base['n_crit']}"),
            ("Бюджет", f"{used} из {budget}", f"осталось {budget - used}"),
        ]
    else:
        reasons = "; ".join(error["message"] for error in result["errors"])
        st.markdown(
            f'<div class="akim-lead bad"><b>Сценарий пока нельзя принять:</b> {esc(reasons)}. '
            "Исправьте выбор во вкладке 1 — и увидите результат.</div>",
            unsafe_allow_html=True,
        )
        cards = [
            ("Индекс качества жизни (Astana Quality of Life Score)", "—", f"сейчас {fmt(base['score'])}"),
            ("Отстающий район", "—", "появится после исправления"),
            ("Острые проблемы — показатели ниже 40", "—", f"сейчас {base['n_crit']}"),
            ("Бюджет", f"{used} из {budget}", "превышен" if used > budget else f"осталось {budget - used}"),
        ]
    st.markdown(
        '<div class="akim-cards">'
        + "".join(f'<div class="akim-card"><div class="t">{t}</div><div class="v">{v}</div>'
                  f'<div class="s">{s}</div></div>' for t, v, s in cards)
        + "</div>",
        unsafe_allow_html=True,
    )

# ---------- Вкладка 1: что изменилось ----------
with tab_plan:
    with result_col:
        st.subheader("Что изменилось в городе")
        components.html(city_html(result, base, data["indicators"]), height=820)
        if not result["valid"]:
            st.info("Результат появится, когда набор будет соответствовать правилам (слева).")
        else:
            st.markdown("**Острые проблемы** — показатели ниже 40 дают штраф −1 к индексу")
            problems = []
            for item in result["resolved_critical"]:
                problems.append(
                    f'<div class="akim-row"><span>{esc(item["district"])} · {esc(indicator_name[item["indicator"]])}'
                    f'</span><span>{fmt_short(item["before"])} → {fmt_short(item["after"])} '
                    f'<span class="chip good">решена</span></span></div>'
                )
            for item in result["critical"]:
                label = "новая" if item in result["new_critical"] else "осталась"
                problems.append(
                    f'<div class="akim-row"><span>{esc(item["district"])} · {esc(indicator_name[item["indicator"]])}'
                    f'</span><span>{fmt_short(item["value"])} <span class="chip bad">{label}</span></span></div>'
                )
            if problems:
                st.markdown("".join(problems), unsafe_allow_html=True)
            else:
                st.caption("Острых проблем не было и нет.")

            st.markdown("**Какое решение дало больше всего** — насколько упадёт индекс, если его убрать")
            contributions = sorted(result["contributions"], key=lambda item: -item["score_contribution"])
            top_value = max((item["score_contribution"] for item in contributions), default=0) or 1
            bars = []
            for item in contributions:
                width = max(item["score_contribution"], 0) / top_value * 100
                bars.append(
                    f'<div class="akim-row" style="display:block"><div style="display:flex;justify-content:'
                    f'space-between"><span>{esc(item["name"])} — {esc(place(item))}</span>'
                    f'<b>{signed(item["score_contribution"])}</b></div>'
                    f'<div class="bar" style="width:{width:.0f}%"></div></div>'
                )
            st.markdown("".join(bars), unsafe_allow_html=True)

            for synergy in result["synergies"]:
                first, second = (measure_by_id[code]["name"] for code in synergy["pair"])
                st.info(
                    f"Решения усиливают друг друга: «{first}» + «{second}» — "
                    f"{indicator_name[synergy['indicator']].lower()} ({place(synergy)}) +{synergy['bonus']}."
                )

            with st.expander("Все 10 показателей по районам: было → стало"):
                st.caption("Красный — острая проблема (ниже 40), жёлтый — на грани (40–45), жирный — изменилось.")
                header = "".join(f"<th>{esc(name)}</th>" for name in district_names)
                body = []
                for code in indicator_codes:
                    cells = []
                    for name in district_names:
                        before = districts_after[name]["values_before"][code]
                        after = districts_after[name]["values_after"][code]
                        color = "#FDECEA" if after < 40 else ("#FFF4D6" if after <= 45 else "#FFFFFF")
                        weight = "700" if before != after else "400"
                        text = fmt_short(after) if before == after else f"{fmt_short(before)} → {fmt_short(after)}"
                        cells.append(f'<td style="background:{color};font-weight:{weight}">{text}</td>')
                    body.append(f"<tr><th>{esc(indicator_name[code])}</th>{''.join(cells)}</tr>")
                d_cells = "".join(
                    f"<td><b>{fmt(districts_after[name]['d_before'])} → {fmt(districts_after[name]['d_after'])}</b></td>"
                    for name in district_names
                )
                body.append(f"<tr><th>Балл района</th>{d_cells}</tr>")
                st.markdown(
                    f'<div class="akim-table"><table><thead><tr><th>Показатель</th>{header}</tr></thead>'
                    f"<tbody>{''.join(body)}</tbody></table></div>",
                    unsafe_allow_html=True,
                )

# ---------- Вкладка 2: совет ИИ-агента ----------
with tab_agent:
    if not result["valid"]:
        st.info("Агент разбирает только допустимый сценарий — исправьте выбор во вкладке 1.")
    else:
        key = plan_key(plan)
        if st.session_state.get("explain_key") != key:
            with st.spinner("Агент готовит разбор…"):
                st.session_state["explanation"] = akim.explain(plan)
            st.session_state["explain_key"] = key
        explanation = st.session_state["explanation"]
        source = (
            "Разбор написал ИИ по расчётам программы, каждое число сверено"
            if explanation["mode"] == "llm"
            else "Разбор составлен программой по расчётам (без ИИ-модели — так работает и без ключа)"
        )
        st.subheader("Разбор вашего сценария")
        st.caption(source + (f". {explanation['note']}" if explanation.get("note") else ""))
        good_col, risk_col, next_col = st.columns(3)
        for column, title, items, kind in (
            (good_col, "Что получилось", explanation["strengths"], st.success),
            (risk_col, "Где риск", explanation["risks"], st.warning),
            (next_col, "Что будет дальше", explanation["consequences"], st.info),
        ):
            with column:
                st.markdown(f"**{title}**")
                for item in items:
                    kind(plain(item))

        st.subheader("Как сделать лучше")
        st.markdown('<div class="akim-step">Агент пробует заменить одну меру и берёт лучшую замену.</div>',
                    unsafe_allow_html=True)
        if st.button("Найти улучшение", key="improve_plan", type="primary"):
            st.session_state["improvement"] = akim.improve(plan)
        improvement = st.session_state.get("improvement")
        if improvement:
            if improvement.get("better") and improvement.get("best"):
                proposal = improvement["best"]
                st.success(
                    f"Совет: {swap_words(proposal['replace'], proposal['with'])}. Индекс "
                    f"{fmt(improvement['current_score'])} → {fmt(proposal['score'])} ({signed(proposal['delta'])})."
                )
                st.button("Применить улучшение", key="apply_improvement", on_click=apply_plan,
                          args=(proposal["plan"],))
            else:
                st.info("Заменой одной меры этот сценарий уже не улучшить.")

        st.subheader("Поручение агенту")
        st.markdown(
            '<div class="akim-step">Скажите цель своими словами — агент переберёт все 694 395 допустимых '
            "вариантов, сам проверит ваши условия и покажет, сколько баллов они стоят.</div>",
            unsafe_allow_html=True,
        )
        mission_text = st.text_input(
            "Поручение", value="Улучши, но не ухудшай качество воздуха в Сарыарке", key="mission_text",
            help="Например: «Школу в Нуре сохрани, ЛРТ исключи, потрать не больше 95»",
        )
        if st.button("Выполнить поручение", key="run_mission", type="primary"):
            request = akim.parse_request(mission_text, plan)
            st.session_state["mission_result"] = akim.run_mission(plan, request)
        mission = st.session_state.get("mission_result")
        if mission:
            st.markdown("Агент понял так: " + " · ".join(f"**{esc(plain(item))}**" for item in mission["constraints"]))
            with st.status("Как агент работал — шаги по порядку", expanded=False,
                           state="error" if mission["status"] == "infeasible" else "complete"):
                for step in mission["steps"]:
                    st.markdown(f"**{step['role']}** — {plain(step['action'])}: {plain(step['result'])}")
            if mission["status"] == "infeasible":
                st.error("Такие условия выполнить нельзя. " + plain(mission["text"]))
            else:
                recommendation = mission["recommendation"]
                st.success(
                    f"Рекомендация: индекс {fmt(recommendation['score'])} при затратах {recommendation['cost']}. "
                    f"{plan_words(recommendation['plan'])}."
                )
                price_col, text_col = st.columns([1, 3])
                price_col.metric("Цена ваших условий", f"{fmt(mission['price'])} балла",
                                 help="На столько баллов лучший вариант без ваших условий выше рекомендации")
                with text_col:
                    for warning in mission["warnings"]:
                        st.warning("Что ухудшится: " + plain(warning))
                st.button("Применить рекомендацию", key="mission_apply", on_click=apply_plan,
                          args=(mission["suggestion"],), type="primary")

        st.subheader("Вопрос агенту")
        st.markdown('<div class="akim-step">Например: «почему такой результат?», «что с Нурой?», '
                    "«сколько осталось?», «что если убрать чистое топливо?»</div>", unsafe_allow_html=True)
        voice = st.audio_input("Или скажите голосом (работает с ключом OpenAI)", key="voice_input")
        if voice is not None and voice.getvalue() != st.session_state.get("processed_voice"):
            st.session_state["processed_voice"] = voice.getvalue()
            try:
                st.session_state["pending_question"] = akim.transcribe(voice.getvalue())
            except RuntimeError as error:
                st.caption(str(error))
        question = st.chat_input("Ваш вопрос агенту", key="chat_prompt") or st.session_state.pop(
            "pending_question", None
        )
        if question:
            history = [{"role": item["role"], "content": item["content"]} for item in st.session_state["chat_history"]]
            answer = akim.chat(question, plan, history)
            st.session_state["chat_history"] += [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer["reply"], "response": answer},
            ]
        for number, message in enumerate(st.session_state["chat_history"][-6:]):
            with st.chat_message(message["role"]):
                st.write(plain(message["content"]))
                response = message.get("response")
                if response and response.get("tools_used"):
                    st.caption("Агент использовал: " + " → ".join(response["tools_used"]))
                if response and response.get("suggestion") and not response.get("mission"):
                    st.button("Применить предложение", key=f"chat_apply_{number}", on_click=apply_plan,
                              args=(response["suggestion"],))

# ---------- Вкладка 3: проверка на прочность ----------
with tab_check:
    events_tab, best_tab, search_tab, compare_tab = st.tabs(
        ["Городские события", "Лучшие варианты", "Подбор под условия", "Сравнить с сохранённым"]
    )
    with events_tab:
        st.markdown('<div class="akim-step">Что будет с вашим сценарием, если в городе что-то случится.</div>',
                    unsafe_allow_html=True)
        events = akim.events()
        event_by_id = {event["id"]: event for event in events}
        event_id = st.selectbox("Событие", list(event_by_id), format_func=lambda item: event_by_id[item]["name"],
                                key="event_select")
        st.caption(event_by_id[event_id]["description"])
        if st.button("Проверить сценарий", key="stress_test", type="primary", disabled=not result["valid"]):
            st.session_state["stress_result"] = akim.stress_test(plan, event_id)
        stress = st.session_state.get("stress_result")
        if stress:
            st.markdown(
                f"**{esc(stress['event']['name'])}:** индекс {fmt(stress['score_before'])} → "
                f"**{fmt(stress['score_after'])}** ({signed(stress['delta'])})."
            )
            for item in stress["new_critical"]:
                st.error(f"Новая острая проблема: {item['district']} · {item['name']} — {fmt_short(item['value'])}")
            advice = stress.get("advice")
            if advice:
                st.success(f"Совет на этот случай: {swap_words(advice['replace'], advice['with'])} — "
                           f"индекс при событии {fmt(advice['score'])} ({signed(advice['delta'])}).")
                st.button("Применить совет", key="stress_apply", on_click=apply_plan, args=(advice["plan"],))
    with best_tab:
        if result["valid"]:
            position = akim.rank(plan)
            st.markdown(
                f"Ваш сценарий — **{position['rank']:,}-й из {position['total']:,}** допустимых вариантов; "
                f"лучший даёт **{fmt(position['best_score'])}**.".replace(",", " ")
                .replace(f" {fmt(position['best_score']).replace(',', ' ')}", f" {fmt(position['best_score'])}")
            )
        for number, option in enumerate(akim.top(5), start=1):
            with st.container(border=True):
                text_col, button_col = st.columns([4, 1])
                text_col.markdown(f"**{number}. Индекс {fmt(option['score'])}**, затраты {option['cost']}  \n"
                                  f"{plan_words(option['plan'])}")
                button_col.button("Взять", key=f"take_top_{number - 1}", on_click=apply_plan, args=(option["plan"],))
    with search_tab:
        st.markdown('<div class="akim-step">Задайте условия — агент найдёт 5 лучших вариантов среди всех.</div>',
                    unsafe_allow_html=True)
        budget_col, floor_col = st.columns(2)
        max_budget = budget_col.slider("Бюджет не больше", 40, 100, 100, key="target_budget")
        floor = floor_col.slider("Ни один район не ниже (балл)", 0, 60, 0, key="target_floor")
        include_col, exclude_col = st.columns(2)
        include = include_col.multiselect("Обязательно взять", measure_ids, format_func=lambda i: measure_by_id[i]["name"],
                                          key="target_include")
        exclude = exclude_col.multiselect("Не брать", measure_ids, format_func=lambda i: measure_by_id[i]["name"],
                                          key="target_exclude")
        if st.button("Найти варианты", key="find_target", type="primary"):
            st.session_state["target_results"] = akim.find_best(
                max_budget=max_budget, include=include, exclude=exclude, min_district_d=floor or None, n=5
            )
        found = st.session_state.get("target_results")
        if found is not None and not found:
            st.warning("При таких условиях допустимых вариантов нет — ослабьте условия.")
        for number, option in enumerate(found or []):
            with st.container(border=True):
                text_col, button_col = st.columns([4, 1])
                text_col.markdown(f"**Индекс {fmt(option['score'])}**, затраты {option['cost']}, отстающий район — "
                                  f"{option['weakest_district']['name']} ({fmt(option['weakest_district']['d'])})  \n"
                                  f"{plan_words(option['plan'])}")
                button_col.button("Взять", key=f"take_target_{number}", on_click=apply_plan, args=(option["plan"],))
        st.markdown("**Сколько индекса можно купить за бюджет** — лучший вариант при каждой сумме затрат")
        st.line_chart(
            [{"Затраты": point["cost"], "Лучший индекс": point["score"]} for point in akim.frontier()],
            x="Затраты", y="Лучший индекс",
        )
    with compare_tab:
        st.markdown('<div class="akim-step">Сохраните текущий сценарий, поменяйте решения — и сравните.</div>',
                    unsafe_allow_html=True)
        if st.button("Сохранить текущий как вариант A", key="remember_a", disabled=not result["valid"]):
            st.session_state["comparison_a"] = [dict(item) for item in plan]
        saved = st.session_state.get("comparison_a")
        if saved and result["valid"]:
            comparison = akim.compare(saved, plan)
            st.markdown(
                f"Вариант A: **{fmt(comparison['a']['score'])}** · сейчас: **{fmt(comparison['b']['score'])}** · "
                f"разница {signed(comparison['score_diff'])}"
            )
            for district in comparison["districts"]:
                st.markdown(f"- {district['name']}: {fmt(district['d_a'])} → {fmt(district['d_b'])} "
                            f"({signed(district['diff'])})")
            if comparison["only_in_a"]:
                st.caption("Было только в A: " + plan_words(comparison["only_in_a"]))
            if comparison["only_in_b"]:
                st.caption("Есть только сейчас: " + plan_words(comparison["only_in_b"]))

# ---------- Вкладка 4: утвердить и рейтинг ----------
with tab_decide:
    approve_col, rating_col = st.columns(2, gap="large")
    with approve_col:
        st.subheader("Утвердить сценарий")
        st.markdown('<div class="akim-step">Агент только советует — утверждает человек.</div>',
                    unsafe_allow_html=True)
        if st.button("Утвердить", key="approve_plan", type="primary", disabled=not result["valid"]):
            try:
                approval = akim.approve(plan)
                st.success(f"Утверждено {approval['approved_at']}: индекс {fmt(approval['score'])}.")
            except ValueError as error:
                st.error(str(error))
        if result["valid"]:
            st.download_button("Скачать паспорт сценария для акима", akim.brief(plan), file_name="pasport_scenariya.md",
                               mime="text/markdown", key="download_brief")
        history = akim.approved()
        if history:
            with st.expander(f"Утверждённые сценарии: {len(history)}"):
                for item in reversed(history):
                    st.markdown(f"- {item['approved_at']} — индекс {fmt(item['score'])}, затраты {item['budget_used']}")
    with rating_col:
        st.subheader("Рейтинг команд")
        st.markdown('<div class="akim-step">Бюджет и данные у всех одинаковые — видно, чьё решение лучше.</div>',
                    unsafe_allow_html=True)
        team = st.text_input("Название команды", key="team_name", placeholder="Например: Terricon")
        if st.button("Отправить в рейтинг", key="submit_team", disabled=not result["valid"]):
            try:
                akim.submit(team, plan)
            except ValueError as error:
                st.error(str(error))
        board = akim.leaderboard()
        if board:
            st.dataframe(
                [
                    {"Место": row["place"], "Команда": row["team"], "Индекс": fmt(row["score"]),
                     "Прирост": signed(row["delta"]), "Место среди всех вариантов": row["rank"],
                     "Затраты": row["budget_used"], "Отстающий район": row["weakest"]["name"]}
                    for row in board
                ],
                hide_index=True, use_container_width=True,
            )
        else:
            st.caption("Пока никто не отправил сценарий.")
