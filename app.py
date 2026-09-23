import html

import streamlit as st

import akim


EXAMPLE_PLAN = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]


def _measure_label(measure: dict, direction_names: dict[str, str]) -> str:
    effects = ", ".join(f"{code} {value:+g}" for code, value in measure["effects"].items())
    return (
        f"{measure['id']} · {measure['name']} · {direction_names[measure['direction']]} · "
        f"{measure['cost']} ед. · лаг {measure['lag']} кв. · {effects}"
    )


def _value_style(before: float, after: float) -> str:
    if after < 40:
        color = "#fee2e2"
    elif after <= 45:
        color = "#fef3c7"
    else:
        color = "transparent"
    weight = "700" if before != after else "400"
    return f"background:{color};font-weight:{weight}"


def _district_table(districts: list[dict], indicator_codes: list[str]) -> str:
    headers = "".join(f"<th>{html.escape(code)}</th>" for code in indicator_codes)
    rows = []
    for district in districts:
        cells = []
        for code in indicator_codes:
            before = district["values_before"][code]
            after = district["values_after"][code]
            cells.append(
                f'<td style="{_value_style(before, after)}">{before:.2f} → {after:.2f}</td>'
            )
        rows.append(
            "<tr>"
            f"<th>{html.escape(district['name'])}<br>"
            f"<small>D {district['d_before']:.2f} → {district['d_after']:.2f}</small></th>"
            f"{''.join(cells)}</tr>"
        )
    return (
        '<div class="district-table"><table><thead><tr><th>Район</th>'
        f"{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _apply_plan(plan: list[dict]) -> None:
    st.session_state["plan"] = [item.copy() for item in plan]
    for index, item in enumerate(plan):
        st.session_state[f"measure_{index}"] = item["measure"]
        district_key = f"district_{index}"
        if item.get("district") is None:
            st.session_state.pop(district_key, None)
        else:
            st.session_state[district_key] = item["district"]
    st.rerun()


def _plan_caption(plan: list[dict], names: dict[str, dict]) -> str:
    return "; ".join(
        f"{item['measure']} · {names[item['measure']]['name']} — {item.get('district') or 'весь город'}"
        for item in plan
    )


def _render_mission(mission: dict, names: dict[str, dict], key_prefix: str) -> None:
    st.markdown("**Понятые условия**")
    for constraint in mission["constraints"]:
        st.markdown(f"- {constraint}")

    state = "error" if mission["status"] == "infeasible" else "complete"
    with st.status("Журнал шагов агента", expanded=True, state=state):
        for step in mission["steps"]:
            st.markdown(f"**{step['role']} · {step['action']}**  \n{step['result']}")

    if mission["status"] == "infeasible":
        st.error("Условия невыполнимы")
        st.write(mission["text"])
        return

    recommendation = mission["recommendation"]
    st.success(mission["text"])
    rec_col, alt_col = st.columns(2)
    with rec_col:
        st.markdown("**Рекомендация**")
        st.write(
            f"Score {recommendation['score']:.2f} · бюджет {recommendation['cost']} · "
            f"место {recommendation['rank']}"
        )
        st.caption(_plan_caption(recommendation["plan"], names))
    with alt_col:
        st.markdown("**Альтернатива**")
        alternative = mission.get("alternative")
        if alternative:
            st.write(
                f"Score {alternative['score']:.2f} · бюджет {alternative['cost']} · "
                f"место {alternative['rank']}"
            )
            st.caption(_plan_caption(alternative["plan"], names))
        else:
            st.caption("Другого подходящего варианта нет.")

    st.metric("Цена ваших условий", f"{mission['price']:.2f} балла")
    if mission["warnings"]:
        st.markdown("**Что ухудшится относительно текущего сценария**")
        for warning in mission["warnings"]:
            st.warning(warning)

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
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    .district-table {overflow-x: auto;}
    .district-table table {border-collapse: collapse; width: 100%; font-size: .82rem;}
    .district-table th, .district-table td {border: 1px solid #d9dee8; padding: .55rem; text-align: center;}
    .district-table thead th {background: #f4f6fa;}
    .district-table tbody th {text-align: left; white-space: nowrap;}
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
indicator_codes = [indicator["code"] for indicator in data["indicators"]]

if "plan" not in st.session_state:
    st.session_state["plan"] = [item.copy() for item in EXAMPLE_PLAN]
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

st.title("Аким на 5 часов")
st.caption(
    "Соберите ровно пять решений. Движок проверит правила и покажет влияние на Astana Quality of Life Score."
)

selector_col, result_col = st.columns([1.05, 1.45], gap="large")

with selector_col:
    st.subheader("Пять управленческих решений")
    selected_plan = []
    for index, current in enumerate(st.session_state["plan"]):
        measure_id = st.selectbox(
            f"Мера {index + 1}",
            measure_ids,
            index=measure_ids.index(current["measure"]),
            format_func=lambda item_id: _measure_label(measure_by_id[item_id], direction_names),
            key=f"measure_{index}",
        )
        measure = measure_by_id[measure_id]
        if measure["scope"] == "district":
            current_district = current.get("district")
            district_index = district_names.index(current_district) if current_district in district_names else 0
            district = st.selectbox(
                f"Район {index + 1}",
                district_names,
                index=district_index,
                key=f"district_{index}",
            )
        else:
            district = None
            st.caption("Городская мера применяется ко всем районам.")
        selected_plan.append({"measure": measure_id, "district": district})

    st.session_state["plan"] = selected_plan

result = akim.evaluate(st.session_state["plan"])

with selector_col:
    st.subheader("Бюджет и правила")
    st.progress(
        min(result["budget_used"], result["budget"]),
        text=f"Потрачено {result['budget_used']} из {result['budget']} · остаток {result['budget_left']}",
    )
    if result["valid"]:
        st.success("Набор допустим")
    else:
        for error in result["errors"]:
            st.error(error["message"])

with result_col:
    st.subheader("Результат сценария")
    if not result["valid"]:
        st.info("Исправьте нарушения — после этого движок рассчитает Score и изменения районов.")
    else:
        score_col, weak_col, critical_col = st.columns(3)
        score_col.metric(
            "Astana Quality of Life Score",
            f"{result['score']:.2f}",
            f"{result['delta']:+.2f} к базе {result['base_score']:.2f}",
        )
        weakest = result["min_district"]
        weakest_row = next(district for district in result["districts"] if district["name"] == weakest["name"])
        weak_col.metric(
            "Самый слабый район",
            weakest["name"],
            f"{weakest_row['d_before']:.2f} → {weakest_row['d_after']:.2f}",
            delta_color="off",
        )
        critical_col.metric(
            "Показателей ниже 40",
            str(result["n_crit"]),
            f"было {base['n_crit']}",
            delta_color="off",
        )

        st.subheader("Районы и показатели: до → после")
        st.caption("Красный — ниже 40, жёлтый — 40–45, жирный — значение изменилось.")
        st.markdown(_district_table(result["districts"], indicator_codes), unsafe_allow_html=True)

        st.subheader("Вклад решений в Score")
        contribution_rows = [
            {
                "Мера": contribution["measure"],
                "Название": contribution["name"],
                "Район": contribution["district"] or "Весь город",
                "Стоимость": contribution["cost"],
                "Вклад в Score": contribution["score_contribution"],
            }
            for contribution in result["contributions"]
        ]
        st.table(contribution_rows)

        st.subheader("Синергии")
        if result["synergies"]:
            for synergy in result["synergies"]:
                district = synergy["district"] or "весь город"
                st.success(
                    f"{synergy['pair'][0]} + {synergy['pair'][1]}: "
                    f"{synergy['indicator']} +{synergy['bonus']} · {district}"
                )
        else:
            st.caption("В этом сценарии синергии не сработали.")

st.divider()
st.header("Разбор и рекомендации агента")

if not result["valid"]:
    st.info("Соберите допустимый набор, чтобы получить разбор и рекомендации агента.")
else:
    explanation = akim.explain(st.session_state["plan"])
    mode_label = "модель" if explanation["mode"] == "llm" else "шаблон (без ключа)"
    st.caption(f"Источник разбора: {mode_label}")
    if explanation.get("note"):
        st.caption(explanation["note"])

    strength_col, risk_col, consequence_col = st.columns(3)
    with strength_col:
        st.subheader("Сильные стороны")
        for item in explanation["strengths"]:
            st.success(item)
    with risk_col:
        st.subheader("Риски")
        for item in explanation["risks"]:
            st.warning(item)
    with consequence_col:
        st.subheader("Последствия")
        for item in explanation["consequences"]:
            st.info(item)
    st.write(explanation["text"])

    if st.button("Улучшить сценарий", key="improve_plan"):
        st.session_state["improvement"] = akim.improve(st.session_state["plan"])
    improvement = st.session_state.get("improvement")
    if improvement:
        if improvement.get("better") and improvement.get("best"):
            proposal = improvement["best"]
            old = proposal["replace"]
            new = proposal["with"]
            st.info(
                f"Заменить {old['measure']} ({old['district'] or 'весь город'}) на "
                f"{new['measure']} ({new['district'] or 'весь город'}): "
                f"Score {improvement['current_score']:.2f} → {proposal['score']:.2f} "
                f"({proposal['delta']:+.2f})."
            )
            st.button(
                "Применить улучшение",
                key="apply_improvement",
                on_click=_apply_plan,
                args=(proposal["plan"],),
                type="primary",
            )
        else:
            st.info(improvement.get("reason", "Замена одной меры не улучшает этот сценарий."))

st.divider()
mission_col, chat_col = st.columns(2, gap="large")

with mission_col:
    st.header("Поручение агенту")
    mission_text = st.text_area(
        "Опишите цель и ограничения",
        value="Улучши, но не ухудшай качество воздуха в Сарыарке",
        placeholder="Школу в Нуре сохрани, ЛРТ исключи, потрать не больше 95",
        key="mission_text",
    )
    if st.button("Выполнить поручение", key="run_mission", type="primary"):
        request = akim.parse_request(mission_text, st.session_state["plan"])
        st.session_state["mission_request"] = request
        st.session_state["mission_result"] = akim.run_mission(st.session_state["plan"], request)
    mission_result = st.session_state.get("mission_result")
    if mission_result:
        _render_mission(mission_result, measure_by_id, "mission")

with chat_col:
    st.header("Чат с агентом")
    st.caption("Спросите о бюджете, рисках, районе или возможной замене.")
    voice = st.audio_input("Голосовое поручение", key="voice_input")
    st.caption("Голос работает с ключом OpenAI; без ключа напишите поручение текстом.")
    if voice is not None:
        audio_bytes = voice.getvalue()
        if audio_bytes != st.session_state.get("processed_voice"):
            st.session_state["processed_voice"] = audio_bytes
            try:
                transcript = akim.transcribe(audio_bytes)
            except RuntimeError as error:
                st.caption(str(error))
            else:
                _submit_chat(transcript)
                st.rerun()

    for message_index, message in enumerate(st.session_state["chat_history"]):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            response = message.get("response")
            if response:
                if response.get("tools_used"):
                    st.caption("Инструменты: " + " → ".join(response["tools_used"]))
                if response.get("note"):
                    st.caption(response["note"])
                if response.get("mission"):
                    _render_mission(response["mission"], measure_by_id, f"chat_{message_index}")
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

st.divider()
st.header("Сравнение и выбор сценария")
comparison_col, top_col = st.columns([1, 1.25], gap="large")

with comparison_col:
    st.subheader("Сравнение с вариантом A")
    if st.button("Запомнить как A", key="remember_a", disabled=not result["valid"]):
        st.session_state["comparison_a"] = [item.copy() for item in st.session_state["plan"]]
        st.success("Текущий сценарий сохранён как вариант A.")

    comparison_a = st.session_state.get("comparison_a")
    if comparison_a:
        comparison = akim.compare(comparison_a, st.session_state["plan"])
        if comparison["a"]["valid"] and comparison["b"]["valid"]:
            a_col, current_col, diff_col = st.columns(3)
            a_col.metric("Вариант A", f"{comparison['a']['score']:.2f}")
            current_col.metric("Текущий", f"{comparison['b']['score']:.2f}")
            diff_col.metric("Текущий − A", f"{comparison['score_diff']:+.2f}")
            st.table(
                [
                    {
                        "Район": district["name"],
                        "D варианта A": district["d_a"],
                        "D текущего": district["d_b"],
                        "Разница": district["diff"],
                    }
                    for district in comparison["districts"]
                ]
            )
            if comparison["only_in_a"]:
                st.caption("Только в A: " + _plan_caption(comparison["only_in_a"], measure_by_id))
            if comparison["only_in_b"]:
                st.caption("Только в текущем: " + _plan_caption(comparison["only_in_b"], measure_by_id))
        else:
            st.warning("Текущий сценарий недопустим — исправьте его для сравнения с вариантом A.")
    else:
        st.caption("Сохраните допустимый сценарий, затем измените набор и сравните результаты.")

with top_col:
    st.subheader("Топ-5 сценариев")
    for place, top_plan in enumerate(akim.top(5), start=1):
        with st.container(border=True):
            metric_col, budget_col = st.columns(2)
            metric_col.metric(f"Топ {place}", f"{top_plan['score']:.2f}")
            budget_col.metric("Бюджет", str(top_plan["cost"]))
            st.caption(_plan_caption(top_plan["plan"], measure_by_id))
            st.button(
                "Взять этот набор",
                key=f"take_top_{place - 1}",
                on_click=_apply_plan,
                args=(top_plan["plan"],),
            )

st.divider()
st.header("Утверждение сценария")
st.caption("Агент готовит варианты, но итоговое решение фиксирует управленец.")

if st.button(
    "Утвердить сценарий",
    key="approve_plan",
    type="primary",
    disabled=not result["valid"],
):
    try:
        st.session_state["latest_approval"] = akim.approve(st.session_state["plan"])
    except ValueError as error:
        st.error(str(error))

latest_approval = st.session_state.get("latest_approval")
if latest_approval:
    st.success(
        f"Сценарий утверждён {latest_approval['approved_at']} · "
        f"Score {latest_approval['score']:.2f}"
    )

approved_plans = akim.approved()
st.subheader("История утверждений")
if approved_plans:
    for approval_index, approval in enumerate(approved_plans, start=1):
        with st.expander(
            f"{approval_index}. {approval['approved_at']} · Score {approval['score']:.2f} · "
            f"бюджет {approval['budget_used']}"
        ):
            st.write(_plan_caption(approval["plan"], measure_by_id))
            if approval.get("note"):
                st.caption(approval["note"])
else:
    st.caption("Утверждённых сценариев пока нет.")
