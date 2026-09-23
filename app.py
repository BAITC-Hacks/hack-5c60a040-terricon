import html
import re

import streamlit as st

import akim


EXAMPLE_PLAN = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]


def _fmt(value: float | int) -> str:
    """Format engine numbers for a Russian-language interface."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _signed(value: float | int) -> str:
    prefix = "+" if value > 0 else "−" if value < 0 else ""
    return prefix + _fmt(abs(value))


def _measure_name(measure: dict | str) -> str:
    name = measure["name"] if isinstance(measure, dict) else measure
    return name.replace(" (расширение Safe City)", "")


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _quarters(value: int) -> str:
    if value % 10 == 1 and value % 100 != 11:
        word = "квартал"
    elif value % 10 in (2, 3, 4) and value % 100 not in (12, 13, 14):
        word = "квартала"
    else:
        word = "кварталов"
    return f"{value} {word}"


def _measure_label(measure: dict) -> str:
    return f"{_measure_name(measure)} — {measure['cost']} из 100"


def _measure_details(
    measure: dict,
    direction_names: dict[str, str],
    indicator_names: dict[str, str],
) -> str:
    effects = " · ".join(
        f"{_lower_first(indicator_names[code])} {_signed(value)}"
        for code, value in measure["effects"].items()
    )
    return (
        f"{direction_names[measure['direction']]} · {effects} · "
        f"заработает через {_quarters(measure['lag'])}"
    )


def _humanize(text: object, measures: dict[str, dict], indicators: dict[str, str]) -> str:
    value = str(text)
    for measure_id in sorted(measures, key=len, reverse=True):
        value = re.sub(
            rf"\b{re.escape(measure_id)}\b",
            _measure_name(measures[measure_id]),
            value,
        )
    for code in sorted(indicators, key=len, reverse=True):
        value = re.sub(rf"\b{re.escape(code)}\b", indicators[code], value)
    value = value.replace("Safe City", "городской безопасности")
    value = value.replace("Score", "индекс качества жизни")
    value = value.replace("к индекс качества жизни", "к индексу качества жизни")
    value = re.sub(
        r"лаг\s+(\d+)\s+кв\.?",
        lambda match: f"заработает через {_quarters(int(match.group(1)))}",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\bD\b", "индекс района", value)
    return value


def _value_style(before: float, after: float) -> str:
    if after < 40:
        color = "#FDE8E8"
    elif after <= 45:
        color = "#FFF3C4"
    else:
        color = "transparent"
    weight = "700" if before != after else "400"
    return f"background:{color};font-weight:{weight}"


def _district_table(districts: list[dict], indicators: list[dict]) -> str:
    headers = "".join(f"<th>{html.escape(item['name'])}</th>" for item in districts)
    rows = []
    for indicator in indicators:
        code = indicator["code"]
        cells = []
        for district in districts:
            before = district["values_before"][code]
            after = district["values_after"][code]
            cells.append(
                f'<td style="{_value_style(before, after)}">'
                f"{_fmt(before)} → {_fmt(after)}</td>"
            )
        rows.append(
            f"<tr><th>{html.escape(indicator['name'])}</th>{''.join(cells)}</tr>"
        )

    district_cells = "".join(
        f'<td style="{_value_style(item["d_before"], item["d_after"])}">'
        f"{_fmt(item['d_before'])} → {_fmt(item['d_after'])}</td>"
        for item in districts
    )
    rows.append(f"<tr class=\"district-index\"><th>Индекс района</th>{district_cells}</tr>")
    return (
        '<div class="district-table"><table><thead><tr><th>Показатель</th>'
        f"{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _apply_plan(plan: list[dict]) -> None:
    st.session_state["plan"] = [item.copy() for item in plan]
    for key in ("improvement", "mission_result", "stress_result", "brief_content"):
        st.session_state.pop(key, None)
    for index, item in enumerate(plan):
        st.session_state[f"measure_{index}"] = item["measure"]
        district_key = f"district_{index}"
        if item.get("district") is None:
            st.session_state.pop(district_key, None)
        else:
            st.session_state[district_key] = item["district"]


def _plan_caption(plan: list[dict], measures: dict[str, dict]) -> str:
    return "; ".join(
        f"{_measure_name(measures[item['measure']])} — "
        f"{item.get('district') or 'весь город'}"
        for item in plan
    )


def _district_map(districts: list[dict], show_after: bool) -> str:
    cards = []
    for district in districts:
        value = district["d_after"] if show_after else district["d_before"]
        if value < 50:
            color = "#FDE8E8"
        elif value < 55:
            color = "#FFF3C4"
        else:
            color = "#E3F5F7"
        cards.append(
            f'<div class="district-card" style="background:{color}">'
            f'<strong>{html.escape(district["name"])}</strong>'
            f'<span>Индекс района: {_fmt(value)} из 100</span></div>'
        )
    return '<div class="city-map">' + "".join(cards) + "</div>"


def _render_contributions(contributions: list[dict]) -> None:
    maximum = max((abs(item["score_contribution"]) for item in contributions), default=1)
    for contribution in contributions:
        width = max(4, int(abs(contribution["score_contribution"]) / maximum * 100))
        name = html.escape(_measure_name(contribution["name"]))
        district = contribution["district"] or "весь город"
        amount = _signed(contribution["score_contribution"])
        st.markdown(
            '<div class="contribution">'
            f'<div class="contribution-label"><strong>{name}</strong>'
            f'<span>{html.escape(district)} · {amount} к индексу</span></div>'
            f'<div class="contribution-track"><div style="width:{width}%"></div></div>'
            "</div>",
            unsafe_allow_html=True,
        )


def _render_mission(
    mission: dict,
    measures: dict[str, dict],
    indicators: dict[str, str],
    key_prefix: str,
) -> None:
    clean = lambda value: _humanize(value, measures, indicators)
    st.markdown("**Понятые условия**")
    for constraint in mission["constraints"]:
        st.markdown(f"- {clean(constraint)}")

    state = "error" if mission["status"] == "infeasible" else "complete"
    with st.status("Как агент выполнил поручение", expanded=True, state=state):
        for step in mission["steps"]:
            st.markdown(
                f"**{clean(step['role'])} · {clean(step['action'])}**  \n"
                f"{clean(step['result'])}"
            )

    if mission["status"] == "infeasible":
        st.error("Условия невыполнимы")
        st.write(clean(mission["text"]))
        return

    recommendation = mission["recommendation"]
    st.success(clean(mission["text"]))
    rec_col, alt_col = st.columns(2)
    with rec_col:
        st.markdown("**Рекомендация**")
        st.write(
            f"Индекс {_fmt(recommendation['score'])} · бюджет {recommendation['cost']} из 100 · "
            f"место {recommendation['rank']}"
        )
        st.caption(_plan_caption(recommendation["plan"], measures))
    with alt_col:
        st.markdown("**Другой подходящий вариант**")
        alternative = mission.get("alternative")
        if alternative:
            st.write(
                f"Индекс {_fmt(alternative['score'])} · бюджет {alternative['cost']} из 100 · "
                f"место {alternative['rank']}"
            )
            st.caption(_plan_caption(alternative["plan"], measures))
        else:
            st.caption("Другого подходящего варианта нет.")

    st.metric("Цена ваших условий", f"{_fmt(mission['price'])} балла")
    if mission["warnings"]:
        st.markdown("**Что ухудшится относительно текущего сценария**")
        for warning in mission["warnings"]:
            st.warning(clean(warning))

    st.button(
        "Применить рекомендацию",
        key=f"{key_prefix}_apply",
        on_click=_apply_plan,
        args=(mission["suggestion"],),
        type="primary",
    )


def _submit_chat(message: str) -> None:
    history = st.session_state["chat_history"]
    context = [{"role": item["role"], "content": item["content"]} for item in history]
    answer = akim.chat(message, st.session_state["plan"], context)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer["reply"], "response": answer})


st.set_page_config(page_title="Аким на 5 часов", page_icon="🏙️", layout="wide")
st.markdown(
    """
    <style>
    :root {--sky:#00ABC2; --button:#007E99; --gold:#FEC50C; --ink:#0B2545; --paper:#F7FBFC;}
    .stApp {background:var(--paper); color:var(--ink);}
    .block-container {padding-top:1.25rem; padding-bottom:3rem;}
    .hero {background:var(--sky); color:white; border-bottom:5px solid var(--gold);
           padding:1.2rem 1.5rem; border-radius:.8rem .8rem .2rem .2rem; margin-bottom:1.25rem;}
    .hero h1 {font-size:2.15rem; line-height:1.1; margin:0 0 .35rem; color:white;}
    .hero p {font-size:1.05rem; margin:0; color:white;}
    .main-point {font-size:1.28rem; line-height:1.55; color:var(--ink); margin:.2rem 0 1rem;}
    .main-point strong {color:var(--button);}
    .district-table {overflow-x:auto;}
    .district-table table {border-collapse:collapse; width:100%; font-size:.82rem;}
    .district-table th,.district-table td {border:1px solid #C6E4E8; padding:.55rem; text-align:center;}
    .district-table thead th {background:#DFF4F7; color:var(--ink);}
    .district-table tbody th {text-align:left; min-width:190px;}
    .district-table .district-index th,.district-table .district-index td {border-top:3px solid var(--sky);}
    .city-map {display:grid; grid-template-columns:repeat(3,minmax(130px,1fr)); gap:.75rem; margin:1rem 0;}
    .district-card {border-radius:.75rem; border:1px solid #C6E4E8; padding:1rem; min-height:5.5rem;}
    .district-card strong,.district-card span {display:block;}
    .district-card span {margin-top:.5rem; font-size:.9rem;}
    .contribution {margin:.65rem 0;}
    .contribution-label {display:flex; justify-content:space-between; gap:1rem; font-size:.92rem;}
    .contribution-track {height:.55rem; background:#DDEDEF; border-radius:1rem; overflow:hidden; margin-top:.3rem;}
    .contribution-track div {height:100%; background:var(--sky); border-radius:1rem;}
    div.stButton > button[kind="primary"] {background:var(--button); border-color:var(--button);}
    div[data-testid="stMetric"] {background:white; border:1px solid #C6E4E8; border-top:4px solid var(--gold);
                                 padding:.75rem; border-radius:.65rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

data = akim.load_data()
base = akim.baseline()
measures = data["measures"]
measure_by_id = {measure["id"]: measure for measure in measures}
measure_ids = [measure["id"] for measure in measures]
district_names = [district["name"] for district in data["districts"]]
direction_names = {direction["code"]: direction["name"] for direction in data["directions"]}
indicator_by_code = {indicator["code"]: indicator["name"] for indicator in data["indicators"]}

if "plan" not in st.session_state:
    st.session_state["plan"] = [item.copy() for item in EXAMPLE_PLAN]
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Widget values are available before their tab is drawn on a rerun. Sync them here so
# the summary above the tabs always describes the current selection.
synced_plan = []
for index, current in enumerate(st.session_state["plan"]):
    measure_id = st.session_state.get(f"measure_{index}", current["measure"])
    if measure_id not in measure_by_id:
        measure_id = current["measure"]
    measure = measure_by_id[measure_id]
    if measure["scope"] == "district":
        district = st.session_state.get(f"district_{index}", current.get("district"))
        if district not in district_names:
            district = district_names[0]
    else:
        district = None
    synced_plan.append({"measure": measure_id, "district": district})
st.session_state["plan"] = synced_plan

result = akim.evaluate(st.session_state["plan"])

st.markdown(
    '<div class="hero"><h1>Аким на 5 часов</h1>'
    '<p>Симулятор бюджета Астаны: выберите 5 решений на 100 единиц бюджета — '
    'движок покажет, как изменится жизнь в каждом районе</p></div>',
    unsafe_allow_html=True,
)

st.markdown("### Главное")
if result["valid"]:
    critical_phrase = (
        "Острых проблем не осталось"
        if result["n_crit"] == 0
        else f"Острых проблем осталось {result['n_crit']}"
    )
    st.markdown(
        '<div class="main-point">'
        f"Ваш сценарий поднимает индекс качества жизни Астаны с "
        f"<strong>{_fmt(result['base_score'])}</strong> до <strong>{_fmt(result['score'])}</strong> "
        f"({_signed(result['delta'])}). Отстающий район — <strong>{html.escape(result['min_district']['name'])}</strong>: "
        f"{_fmt(result['min_district']['d'])} из 100. {critical_phrase} "
        f"(было {base['n_crit']}). Потрачено {result['budget_used']} из {result['budget']}."
        "</div>",
        unsafe_allow_html=True,
    )
else:
    reasons = "; ".join(
        _humanize(error["message"], measure_by_id, indicator_by_code)
        for error in result["errors"]
    )
    st.markdown(
        '<div class="main-point"><strong>Сценарий нельзя принять:</strong> '
        f"{html.escape(reasons)}. Исправьте — и увидите результат.</div>",
        unsafe_allow_html=True,
    )

card_score, card_weak, card_critical = st.columns(3)
if result["valid"]:
    card_score.metric(
        "Индекс качества жизни (Astana Quality of Life Score)",
        _fmt(result["score"]),
        f"{_signed(result['delta'])} к исходным {_fmt(result['base_score'])}",
    )
    card_weak.metric(
        "Отстающий район",
        result["min_district"]["name"],
        f"{_fmt(result['min_district']['d'])} из 100",
        delta_color="off",
    )
    card_critical.metric(
        "Острые проблемы — показатели ниже 40 из 100",
        str(result["n_crit"]),
        f"было {base['n_crit']}",
        delta_color="off",
    )
else:
    card_score.metric("Индекс качества жизни (Astana Quality of Life Score)", "—")
    card_weak.metric("Отстающий район", "—")
    card_critical.metric("Острые проблемы — показатели ниже 40 из 100", "—")

scenario_tab, agent_tab, compare_tab, target_tab, districts_tab, events_tab, brief_tab = st.tabs(
    [
        "1. Сценарий",
        "2. Совет агента",
        "3. Сравнить и утвердить",
        "Подбор под цель",
        "Районы",
        "Городские события",
        "Паспорт сценария",
    ]
)

with scenario_tab:
    selector_col, result_col = st.columns([1.05, 1.45], gap="large")
    with selector_col:
        st.header("Выберите пять решений")
        selected_plan = []
        for index, current in enumerate(st.session_state["plan"]):
            measure_id = st.selectbox(
                f"Решение {index + 1}",
                measure_ids,
                index=measure_ids.index(current["measure"]),
                format_func=lambda item_id: _measure_label(measure_by_id[item_id]),
                key=f"measure_{index}",
            )
            measure = measure_by_id[measure_id]
            st.caption(_measure_details(measure, direction_names, indicator_by_code))
            if measure["scope"] == "district":
                current_district = current.get("district")
                district_index = (
                    district_names.index(current_district)
                    if current_district in district_names
                    else 0
                )
                district = st.selectbox(
                    "Где: район",
                    district_names,
                    index=district_index,
                    key=f"district_{index}",
                )
            else:
                district = None
                st.caption("Работает во всех районах города.")
            selected_plan.append({"measure": measure_id, "district": district})
        st.session_state["plan"] = selected_plan

        st.subheader("Бюджет и правила")
        st.progress(
            min(result["budget_used"], result["budget"]),
            text=(
                f"Потрачено {result['budget_used']} из {result['budget']} · "
                f"остаток {result['budget_left']}"
            ),
        )
        if result["valid"]:
            st.success("Набор допустим")
        else:
            for error in result["errors"]:
                st.error(_humanize(error["message"], measure_by_id, indicator_by_code))

    with result_col:
        st.header("Как изменятся районы")
        if not result["valid"]:
            st.info("Исправьте нарушения, чтобы увидеть результат по районам.")
        else:
            st.caption(
                "Красный — острая проблема, ниже 40 · жёлтый — на грани, 40–45 · "
                "жирный — изменилось"
            )
            st.markdown(
                _district_table(result["districts"], data["indicators"]),
                unsafe_allow_html=True,
            )

            st.subheader("Вклад решений")
            _render_contributions(result["contributions"])

            st.subheader("Решения усиливают друг друга")
            if result["synergies"]:
                for synergy in result["synergies"]:
                    first, second = synergy["pair"]
                    district = (
                        f"районе {synergy['district']}"
                        if synergy["district"]
                        else "городе"
                    )
                    st.success(
                        f"{_measure_name(measure_by_id[first])} + "
                        f"{_measure_name(measure_by_id[second])} — "
                        f"{_lower_first(indicator_by_code[synergy['indicator']])} "
                        f"в {district} {_signed(synergy['bonus'])}"
                    )
            else:
                st.caption("В этом сценарии решения не дают дополнительного совместного эффекта.")

with agent_tab:
    st.header("Совет агента")
    if not result["valid"]:
        st.info("Соберите допустимый набор, чтобы получить разбор и рекомендации агента.")
    else:
        explanation_plan = [item.copy() for item in st.session_state["plan"]]
        if st.session_state.get("explanation_plan") != explanation_plan:
            with st.spinner("Агент готовит разбор…"):
                st.session_state["explanation"] = akim.explain(explanation_plan)
                st.session_state["explanation_plan"] = explanation_plan
        explanation = st.session_state["explanation"]
        if explanation["mode"] == "llm":
            st.caption("Разбор написал ИИ по расчётам движка, числа сверены")
        else:
            st.caption("Разбор составлен по расчётам движка")
        if explanation.get("note"):
            st.caption(_humanize(explanation["note"], measure_by_id, indicator_by_code))

        strength_col, risk_col, consequence_col = st.columns(3)
        sections = [
            (strength_col, "Что получилось", "strengths", st.success),
            (risk_col, "Где риск", "risks", st.warning),
            (consequence_col, "Что будет дальше", "consequences", st.info),
        ]
        for column, title, key, renderer in sections:
            with column:
                st.subheader(title)
                for item in explanation[key]:
                    renderer(_humanize(item, measure_by_id, indicator_by_code))
        st.write(_humanize(explanation["text"], measure_by_id, indicator_by_code))

        if st.button("Улучшить сценарий", key="improve_plan"):
            st.session_state["improvement"] = akim.improve(st.session_state["plan"])
        improvement = st.session_state.get("improvement")
        if improvement:
            if improvement.get("better") and improvement.get("best"):
                proposal = improvement["best"]
                old = proposal["replace"]
                new = proposal["with"]
                st.info(
                    f"Заменить {_measure_name(measure_by_id[old['measure']])} "
                    f"({old['district'] or 'весь город'}) на "
                    f"{_measure_name(measure_by_id[new['measure']])} "
                    f"({new['district'] or 'весь город'}): индекс "
                    f"{_fmt(improvement['current_score'])} → {_fmt(proposal['score'])} "
                    f"({_signed(proposal['delta'])})."
                )
                st.button(
                    "Применить улучшение",
                    key="apply_improvement",
                    on_click=_apply_plan,
                    args=(proposal["plan"],),
                    type="primary",
                )
            else:
                st.info(improvement.get("reason", "Замена одного решения не улучшает сценарий."))

    st.divider()
    mission_col, chat_col = st.columns(2, gap="large")
    with mission_col:
        st.subheader("Поручение агенту")
        mission_text = st.text_area(
            "Опишите цель и ограничения",
            value="Улучши, но не ухудшай качество воздуха в Сарыарке",
            placeholder="Школу в Нуре сохрани, ЛРТ исключи, потрать не больше 95",
            key="mission_text",
        )
        if st.button("Выполнить поручение", key="run_mission", type="primary"):
            request = akim.parse_request(mission_text, st.session_state["plan"])
            st.session_state["mission_request"] = request
            st.session_state["mission_result"] = akim.run_mission(
                st.session_state["plan"], request
            )
        mission_result = st.session_state.get("mission_result")
        if mission_result:
            _render_mission(
                mission_result,
                measure_by_id,
                indicator_by_code,
                "mission",
            )

    with chat_col:
        st.subheader("Чат с агентом")
        st.caption("Спросите о бюджете, рисках, районе или возможной замене.")
        voice = st.audio_input("Голосовое поручение", key="voice_input")
        st.caption("Голос доступен при подключённой модели; без неё напишите поручение текстом.")
        if voice is not None:
            audio_bytes = voice.getvalue()
            if audio_bytes != st.session_state.get("processed_voice"):
                st.session_state["processed_voice"] = audio_bytes
                try:
                    transcript = akim.transcribe(audio_bytes)
                except RuntimeError as error:
                    st.caption(_humanize(error, measure_by_id, indicator_by_code))
                else:
                    _submit_chat(transcript)
                    st.rerun()

        for message_index, message in enumerate(st.session_state["chat_history"]):
            with st.chat_message(message["role"]):
                st.write(_humanize(message["content"], measure_by_id, indicator_by_code))
                response = message.get("response")
                if response:
                    if response.get("tools_used"):
                        st.caption("Инструменты: " + " → ".join(response["tools_used"]))
                    if response.get("note"):
                        st.caption(_humanize(response["note"], measure_by_id, indicator_by_code))
                    if response.get("mission"):
                        _render_mission(
                            response["mission"],
                            measure_by_id,
                            indicator_by_code,
                            f"chat_{message_index}",
                        )
                    elif response.get("suggestion"):
                        st.button(
                            "Применить предложение",
                            key=f"chat_{message_index}_apply",
                            on_click=_apply_plan,
                            args=(response["suggestion"],),
                        )

        prompt = st.chat_input("Например: почему такой результат?", key="chat_prompt")
        if prompt:
            _submit_chat(prompt)
            st.rerun()

with compare_tab:
    comparison_col, top_col = st.columns([1, 1.25], gap="large")
    with comparison_col:
        st.header("Сравнить варианты")
        if st.button("Запомнить как вариант А", key="remember_a", disabled=not result["valid"]):
            st.session_state["comparison_a"] = [
                item.copy() for item in st.session_state["plan"]
            ]
            st.success("Текущий сценарий сохранён как вариант А.")

        comparison_a = st.session_state.get("comparison_a")
        if comparison_a:
            comparison = akim.compare(comparison_a, st.session_state["plan"])
            if comparison["a"]["valid"] and comparison["b"]["valid"]:
                a_col, current_col, diff_col = st.columns(3)
                a_col.metric("Вариант А", _fmt(comparison["a"]["score"]))
                current_col.metric("Текущий", _fmt(comparison["b"]["score"]))
                diff_col.metric("Текущий минус А", _signed(comparison["score_diff"]))
                st.table(
                    [
                        {
                            "Район": district["name"],
                            "Вариант А": _fmt(district["d_a"]),
                            "Текущий": _fmt(district["d_b"]),
                            "Разница": _signed(district["diff"]),
                        }
                        for district in comparison["districts"]
                    ]
                )
                if comparison["only_in_a"]:
                    st.caption(
                        "Только в варианте А: "
                        + _plan_caption(comparison["only_in_a"], measure_by_id)
                    )
                if comparison["only_in_b"]:
                    st.caption(
                        "Только в текущем: "
                        + _plan_caption(comparison["only_in_b"], measure_by_id)
                    )
            else:
                st.warning("Исправьте текущий сценарий, чтобы сравнить его с вариантом А.")
        else:
            st.caption("Сохраните сценарий, затем измените набор и сравните результаты.")

    with top_col:
        st.header("Пять лучших сценариев")
        for place, top_plan in enumerate(akim.top(5), start=1):
            with st.container(border=True):
                metric_col, budget_col = st.columns(2)
                metric_col.metric(f"Место {place}", _fmt(top_plan["score"]))
                budget_col.metric("Потрачено", f"{top_plan['cost']} из 100")
                st.caption(_plan_caption(top_plan["plan"], measure_by_id))
                st.button(
                    "Взять этот набор",
                    key=f"take_top_{place - 1}",
                    on_click=_apply_plan,
                    args=(top_plan["plan"],),
                )

    st.divider()
    st.header("Утвердить сценарий")
    st.caption("Агент предлагает варианты, а итоговое решение фиксирует управленец.")
    if st.button(
        "Утвердить",
        key="approve_plan",
        type="primary",
        disabled=not result["valid"],
    ):
        try:
            st.session_state["latest_approval"] = akim.approve(st.session_state["plan"])
        except ValueError as error:
            st.error(_humanize(error, measure_by_id, indicator_by_code))

    latest_approval = st.session_state.get("latest_approval")
    if latest_approval:
        st.success(
            f"Сценарий утверждён {latest_approval['approved_at']} · "
            f"индекс {_fmt(latest_approval['score'])}"
        )

    approved_plans = akim.approved()
    st.subheader("История утверждений")
    if approved_plans:
        for approval_index, approval in enumerate(approved_plans, start=1):
            with st.expander(
                f"{approval_index}. {approval['approved_at']} · индекс {_fmt(approval['score'])} · "
                f"потрачено {approval['budget_used']} из 100"
            ):
                st.write(_plan_caption(approval["plan"], measure_by_id))
                if approval.get("note"):
                    st.caption(_humanize(approval["note"], measure_by_id, indicator_by_code))
    else:
        st.caption("Утверждённых сценариев пока нет.")

with target_tab:
    st.header("Подбор сценария под условия")
    filter_col, include_col, exclude_col, floor_col = st.columns(4)
    max_budget = filter_col.number_input(
        "Бюджет не больше",
        min_value=0,
        max_value=data["budget"],
        value=data["budget"],
        step=1,
        key="target_budget",
    )
    required_measures = include_col.multiselect(
        "Обязательно",
        measure_ids,
        format_func=lambda item_id: _measure_name(measure_by_id[item_id]),
        key="target_include",
    )
    excluded_measures = exclude_col.multiselect(
        "Исключить",
        measure_ids,
        format_func=lambda item_id: _measure_name(measure_by_id[item_id]),
        key="target_exclude",
    )
    district_floor = floor_col.number_input(
        "Индекс каждого района не ниже",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=1.0,
        key="target_floor",
    )
    if st.button("Найти варианты", key="find_target", type="primary"):
        st.session_state["target_results"] = akim.find_best(
            max_budget=max_budget,
            include=required_measures,
            exclude=excluded_measures,
            min_district_d=district_floor if district_floor > 0 else None,
            n=5,
        )
    target_results = st.session_state.get("target_results")
    if target_results is not None:
        if not target_results:
            st.warning("При таких условиях допустимых сценариев не найдено.")
        for target_index, target in enumerate(target_results):
            with st.container(border=True):
                result_col, target_budget_col, weak_target_col = st.columns(3)
                result_col.metric("Индекс качества жизни", _fmt(target["score"]))
                target_budget_col.metric("Потрачено", f"{target['cost']} из 100")
                weak_target_col.metric(
                    "Отстающий район",
                    target["weakest_district"]["name"],
                    f"{_fmt(target['weakest_district']['d'])} из 100",
                    delta_color="off",
                )
                st.caption(_plan_caption(target["plan"], measure_by_id))
                st.button(
                    "Взять",
                    key=f"take_target_{target_index}",
                    on_click=_apply_plan,
                    args=(target["plan"],),
                )

    st.subheader("Как бюджет влияет на лучший результат")
    frontier = [
        {"Бюджет": item["cost"], "Индекс качества жизни": item["score"]}
        for item in akim.frontier()
    ]
    st.line_chart(
        frontier,
        x="Бюджет",
        y="Индекс качества жизни",
        x_label="Бюджет",
        y_label="Индекс качества жизни",
    )

with districts_tab:
    st.header("Пять условных районов")
    st.caption("Это схема для сравнения показателей, а не географическая карта Астаны.")
    map_mode = st.radio(
        "Показать районы",
        ["До решений", "После решений"],
        horizontal=True,
        key="map_mode",
        disabled=not result["valid"],
    )
    st.markdown(
        _district_map(
            result["districts"],
            show_after=result["valid"] and map_mode == "После решений",
        ),
        unsafe_allow_html=True,
    )

    selected_district = st.selectbox(
        "Подробно о районе", district_names, key="district_report_select"
    )
    district_report = akim.district_report(
        selected_district,
        st.session_state["plan"] if result["valid"] else None,
    )
    report_score_col, report_place_col = st.columns(2)
    report_score_col.metric("Индекс района", _fmt(district_report["d"]))
    report_place_col.metric("Место с конца", str(district_report["place_from_bottom"]))
    st.write(district_report["profile"])
    st.markdown("**Слабые показатели**")
    st.table(
        [
            {"Показатель": weak["name"], "Значение": _fmt(weak["value"])}
            for weak in district_report["weak"]
        ]
    )
    st.markdown("**Какие решения помогут сильнее всего**")
    st.table(
        [
            {
                "Решение": _measure_name(option["name"]),
                "Стоимость": f"{option['cost']} из 100",
                "Прирост индекса района": _signed(option["d_gain"]),
                "Прирост индекса города": _signed(option["score_gain"]),
            }
            for option in district_report["best_measures"]
        ]
    )

with events_tab:
    st.header("Проверка неожиданным городским событием")
    event_items = akim.events()
    event_by_id = {event["id"]: event for event in event_items}
    event_id = st.selectbox(
        "Событие",
        list(event_by_id),
        format_func=lambda item_id: event_by_id[item_id]["name"],
        key="event_id",
    )
    st.write(_humanize(event_by_id[event_id]["description"], measure_by_id, indicator_by_code))
    if st.button("Проверить сценарий", key="stress_test", disabled=not result["valid"]):
        st.session_state["stress_result"] = akim.stress_test(
            st.session_state["plan"], event_id
        )
    stress_result = st.session_state.get("stress_result")
    if stress_result:
        before_col, after_col, event_delta_col = st.columns(3)
        before_col.metric("Индекс до события", _fmt(stress_result["score_before"]))
        after_col.metric("Индекс после события", _fmt(stress_result["score_after"]))
        event_delta_col.metric("Изменение", _signed(stress_result["delta"]))
        st.info(_humanize(stress_result["text"], measure_by_id, indicator_by_code))
        if stress_result["new_critical"]:
            st.warning("Появились новые показатели ниже 40.")
        advice = stress_result.get("advice")
        if advice:
            st.button(
                "Применить совет",
                key="apply_event_advice",
                on_click=_apply_plan,
                args=(advice["plan"],),
            )

with brief_tab:
    st.header("Паспорт сценария для акима")
    st.caption("Документ собирается из расчётов движка и текущего разбора агента.")
    if st.button("Подготовить паспорт", key="prepare_brief", disabled=not result["valid"]):
        with st.spinner("Формируем паспорт сценария…"):
            st.session_state["brief_content"] = akim.brief(st.session_state["plan"])
            st.session_state["brief_plan"] = [
                item.copy() for item in st.session_state["plan"]
            ]
    brief_content = st.session_state.get("brief_content")
    if brief_content:
        st.download_button(
            "Скачать паспорт",
            data=brief_content,
            file_name="akim-scenario.md",
            mime="text/markdown",
            key="download_brief",
        )
        with st.expander("Предпросмотр паспорта"):
            st.markdown(_humanize(brief_content, measure_by_id, indicator_by_code))
