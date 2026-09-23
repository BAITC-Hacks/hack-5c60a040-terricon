from pathlib import Path

import akim
import akim.approvals
import akim.teams
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _app(monkeypatch, tmp_path) -> AppTest:
    monkeypatch.setenv("AKIM_NO_LLM", "1")
    monkeypatch.setattr(akim.approvals, "STORE", tmp_path / "approved.json")
    monkeypatch.setattr(akim.teams, "STORE", tmp_path / "teams.json")
    return AppTest.from_file(APP_PATH, default_timeout=60).run()


def _text(app) -> str:
    elements = (*app.markdown, *app.caption, *app.error, *app.warning, *app.info, *app.success)
    return " ".join(element.value for element in elements)


def test_main_message_is_readable_in_five_seconds(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    assert not app.exception
    lead = next(m.value for m in app.markdown if "Главное" in m.value)
    assert "52,56" in lead and "56,54" in lead and "Нура" in lead and "95 из 100" in lead
    for code in ("M7 ·", "T1", "лаг", " ед.", "Score города"):
        assert code not in _text(app)


def test_improvement_applies_without_warnings_and_old_offer_disappears(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.button(key="improve_plan").click().run()
    assert any("57,21" in s.value for s in app.success)
    app.button(key="apply_improvement").click().run()
    assert not app.exception
    assert not [w for w in app.warning if "rerun" in w.value]
    assert "57,21" in next(m.value for m in app.markdown if "Главное" in m.value)
    assert not [b for b in app.button if b.key == "apply_improvement"]


def test_old_advice_disappears_and_signs_and_codes_are_readable(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    assert any("лучший даёт **57,24**" in m.value for m in app.markdown)
    app.button(key="improve_plan").click().run()
    assert [b for b in app.button if b.key == "apply_improvement"]
    app.selectbox(key="district_4").set_value("Есиль").run()
    assert "56,60" in next(m.value for m in app.markdown if "Главное" in m.value)
    assert not [b for b in app.button if b.key == "apply_improvement"]
    app.selectbox(key="measure_4").set_value("M11").run()
    assert any("разгрузка дорог −2" in c.value for c in app.caption)
    assert "+-" not in _text(app)
    app.selectbox(key="measure_4").set_value("M7").run()
    errors = " ".join(e.value for e in app.error)
    assert "выбрано более одного раза" in errors and "M7" not in errors
    assert not app.exception


def test_event_search_and_chat_mission_follow_current_conditions(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.button(key="stress_test").click().run()
    assert any("55,30" in m.value for m in app.markdown)
    app.selectbox(key="event_select").set_value(akim.events()[1]["id"]).run()
    assert not any("55,30" in m.value for m in app.markdown)
    assert not [b for b in app.button if b.key == "stress_apply"]

    app.button(key="find_target").click().run()
    assert [b for b in app.button if b.key.startswith("take_target_")]
    app.slider(key="target_budget").set_value(80).run()
    assert not [b for b in app.button if b.key.startswith("take_target_")]
    assert any("Условия изменились" in c.value for c in app.caption)

    app.chat_input(key="chat_prompt").set_value("Улучши, но не ухудшай качество воздуха в Сарыарке").run()
    assert any("Как агент работал" in e.label for e in app.expander)
    assert [b for b in app.button if b.key.startswith("chat_apply_")]
    app.selectbox(key="district_4").set_value("Есиль").run()
    assert not [b for b in app.button if b.key.startswith("chat_apply_")]

    app.button(key="run_robust").click().run()
    assert any("Самый устойчивый" in m.value and "55,82" in m.value for m in app.markdown)
    app.button(key="take_robust").click().run()
    assert "57,07" in next(m.value for m in app.markdown if "Главное" in m.value)
    assert not app.exception


def test_mission_price_of_conditions(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.button(key="run_mission").click().run()
    assert any("56,78" in s.value for s in app.success)
    assert any(metric.value == "0,46 балла" for metric in app.metric)


def test_best_variant_event_approval_and_team_rating(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.button(key="stress_test").click().run()
    assert any("55,30" in m.value for m in app.markdown)
    app.button(key="take_best").click().run()
    assert "57,24" in next(m.value for m in app.markdown if "Главное" in m.value)
    app.button(key="approve_plan").click().run()
    assert any("57,24" in s.value for s in app.success)
    app.text_input(key="team_name").set_value("Terricon").run()
    app.button(key="submit_team").click().run()
    assert akim.teams.leaderboard()[0]["team"] == "Terricon"
    assert not app.exception


def test_over_budget_is_explained_in_words(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.selectbox(key="measure_4").set_value("M3").run()
    app.selectbox(key="measure_3").set_value("M13").run()
    assert not app.exception
    assert any("нельзя принять" in m.value for m in app.markdown)


def test_district_passport_and_sensitivity_use_engine_values(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)

    tab_labels = [tab.label for tab in app.tabs]
    assert "Паспорт района" in tab_labels
    assert "Если приоритеты сменятся" in tab_labels

    app.selectbox(key="district_report_select").set_value("Нура").run()
    assert not app.exception
    assert any(metric.label == "Балл района" and metric.value == "52,96" for metric in app.metric)
    assert any(metric.label == "Место с конца" and metric.value == "1" for metric in app.metric)

    app.button(key="run_sensitivity").click().run()
    text = _text(app)
    assert "Доступность общественного транспорта" in text
    assert "Поликлиники и первичная медпомощь" in text
    assert "Линия ЛРТ / расширение" in text
    assert "цена 30 · балл района +2,02 · индекс города +0,83" in text
    assert "🚌 Транспорт" in text
    assert "ваш индекс <b>56,41</b> · лучший индекс <b>57,28</b>" in text
    assert "🌳 Экология" in text
    assert "M3" not in text and "T2" not in text
