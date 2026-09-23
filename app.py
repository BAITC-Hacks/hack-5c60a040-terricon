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
