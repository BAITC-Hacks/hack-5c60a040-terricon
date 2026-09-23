import os

import akim
import akim.approvals as approvals
from streamlit.testing.v1 import AppTest


def _app() -> AppTest:
    os.environ["AKIM_NO_LLM"] = "1"
    return AppTest.from_file("app.py", default_timeout=10).run()


def _selectbox(app: AppTest, key: str):
    return next(widget for widget in app.selectbox if widget.key == key)


def _has_callback_rerun_warning(app: AppTest) -> bool:
    return any("Calling st.rerun() within a callback is a no-op" in warning.value for warning in app.warning)


def test_example_plan_shows_budget_validity_and_result():
    app = _app()

    assert not app.exception
    assert any("95 из 100" in progress.proto.text for progress in app.get("progress"))
    assert any(message.value == "Набор допустим" for message in app.success)

    score = next(metric for metric in app.metric if metric.label == "Astana Quality of Life Score")
    weakest = next(metric for metric in app.metric if metric.label == "Самый слабый район")
    assert score.value == "56.54"
    assert "+3.98" in score.delta
    assert weakest.value == "Нура"
    assert "49.18 → 52.96" in weakest.delta


def test_over_budget_plan_shows_engine_error():
    app = _app()
    choices = ["M3", "M13", "M7", "M5", "M6"]

    for index, measure in enumerate(choices):
        _selectbox(app, f"measure_{index}").select(measure)
        app.run()

    errors = [message.value for message in app.error]
    assert any(message.startswith("Бюджет превышен: 127 из 100") for message in errors)
    assert not app.exception


def test_agent_explanation_and_improvement_require_explicit_apply():
    app = _app()
    original_plan = [item.copy() for item in app.session_state["plan"]]

    assert any("шаблон (без ключа)" in caption.value for caption in app.caption)
    next(button for button in app.button if button.label == "Улучшить сценарий").click().run()

    improvement = app.session_state["improvement"]
    assert improvement["better"] is True
    assert improvement["best"]["score"] == 57.21
    assert improvement["best"]["delta"] == 0.67
    assert app.session_state["plan"] == original_plan

    next(button for button in app.button if button.label == "Применить улучшение").click().run()
    assert app.session_state["plan"] == improvement["best"]["plan"]
    assert "improvement" not in app.session_state
    assert not any(button.label == "Применить улучшение" for button in app.button)
    assert not _has_callback_rerun_warning(app)
    assert not app.exception


def test_mission_shows_retry_recommendation_and_price_of_constraints():
    app = _app()
    app.text_area(key="mission_text").set_value("Улучши, но не ухудшай качество воздуха в Сарыарке")
    app.button(key="run_mission").click().run()

    mission = app.session_state["mission_result"]
    checker_steps = [step for step in mission["steps"] if step["role"] == "Проверяющий"]
    assert mission["status"] == "ok"
    assert mission["recommendation"]["score"] == 56.78
    assert mission["price"] == 0.46
    assert mission["retried"] is True
    assert len(checker_steps) == 2
    assert app.status
    assert any("Цена ваших условий" == metric.label and metric.value == "0.46 балла" for metric in app.metric)

    app.button(key="mission_apply").click().run()
    assert "mission_result" not in app.session_state
    assert not any(button.label == "Применить рекомендацию" for button in app.button)
    assert not _has_callback_rerun_warning(app)
    assert not app.exception


def test_chat_uses_engine_and_shows_tools():
    app = _app()
    app.chat_input(key="chat_prompt").set_value("сколько осталось?").run()

    response = app.session_state["chat_history"][-1]["response"]
    assert response["intent"] == "budget"
    assert response["tools_used"] == ["Проверка правил"]
    assert "Потрачено 95 из 100, остаток 5" in response["reply"]
    assert len(app.chat_message) == 2
    assert any("Инструменты: Проверка правил" in caption.value for caption in app.caption)
    assert not app.exception


def test_top_five_and_take_plan_sync_all_widget_keys():
    app = _app()
    top_plan = akim.top(1)[0]

    top_metric = next(metric for metric in app.metric if metric.label == "Топ 1")
    assert top_metric.value == "57.24"
    app.button(key="improve_plan").click().run()
    assert "improvement" in app.session_state
    app.button(key="take_top_0").click().run()

    assert app.session_state["plan"] == top_plan["plan"]
    assert "improvement" not in app.session_state
    for index, item in enumerate(top_plan["plan"]):
        assert app.session_state[f"measure_{index}"] == item["measure"]
        if item["district"] is not None:
            assert app.session_state[f"district_{index}"] == item["district"]
    score = next(metric for metric in app.metric if metric.label == "Astana Quality of Life Score")
    assert score.value == "57.24"
    assert not _has_callback_rerun_warning(app)
    assert not app.exception


def test_remember_a_and_compare_with_current_plan():
    app = _app()
    original_plan = [item.copy() for item in app.session_state["plan"]]
    app.button(key="remember_a").click().run()

    assert app.session_state["comparison_a"] == original_plan
    app.button(key="take_top_0").click().run()

    score_a = next(metric for metric in app.metric if metric.label == "Вариант A")
    score_current = next(metric for metric in app.metric if metric.label == "Текущий")
    assert score_a.value == "56.54"
    assert score_current.value == "57.24"
    assert not app.exception


def test_approve_uses_store_and_lists_approved_plan(monkeypatch, tmp_path):
    store = tmp_path / "approved.json"
    monkeypatch.setattr(approvals, "STORE", store)
    app = _app()

    approve_button = app.button(key="approve_plan")
    assert approve_button.disabled is False
    approve_button.click().run()

    assert store.exists()
    approved = approvals.approved()
    assert len(approved) == 1
    assert approved[0]["score"] == 56.54
    assert app.session_state["latest_approval"]["score"] == 56.54
    assert any("Score 56.54" in message.value for message in app.success)
    assert app.expander
    assert not app.exception


def test_invalid_plan_cannot_be_approved(monkeypatch, tmp_path):
    store = tmp_path / "approved.json"
    monkeypatch.setattr(approvals, "STORE", store)
    app = _app()
    choices = ["M3", "M13", "M7", "M5", "M6"]

    for index, measure in enumerate(choices):
        _selectbox(app, f"measure_{index}").select(measure)
        app.run()

    assert app.button(key="approve_plan").disabled is True
    assert not store.exists()
    assert approvals.approved() == []
    assert not app.exception


def test_explanation_is_cached_until_plan_changes(monkeypatch):
    real_explain = akim.explain
    calls = []

    def tracked_explain(plan):
        calls.append([item.copy() for item in plan])
        return real_explain(plan)

    monkeypatch.setattr(akim, "explain", tracked_explain)
    app = _app()
    assert len(calls) == 1

    app.button(key="remember_a").click().run()
    assert len(calls) == 1

    app.button(key="take_top_0").click().run()
    assert len(calls) == 2
    assert calls[-1] == akim.top(1)[0]["plan"]
    assert not app.exception


def test_v5_target_search_respects_budget_and_passport_downloads():
    app = _app()
    assert [tab.label for tab in app.tabs] == [
        "Подбор под цель",
        "Районы",
        "Городские события",
        "Паспорт сценария",
    ]

    app.number_input(key="target_budget").set_value(80)
    app.button(key="find_target").click().run()
    results = app.session_state["target_results"]
    assert len(results) == 5
    assert all(item["cost"] <= 80 for item in results)

    app.button(key="prepare_brief").click().run()
    assert app.session_state["brief_content"].startswith("# Паспорт сценария")
    downloads = app.get("download_button")
    assert len(downloads) == 1
    assert downloads[0].proto.label == "Скачать паспорт"
    assert not app.exception


def test_v5_district_report_and_city_event():
    app = _app()
    district_score = next(metric for metric in app.metric if metric.label == "D района")
    assert district_score.value == "63.43"

    app.button(key="stress_test").click().run()
    stress = app.session_state["stress_result"]
    assert stress["event"]["id"] == "smog"
    assert stress["score_before"] == 56.54
    assert any(metric.label == "Score после события" for metric in app.metric)
    assert not app.exception
