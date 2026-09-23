from streamlit.testing.v1 import AppTest


def _app() -> AppTest:
    return AppTest.from_file("app.py", default_timeout=10).run()


def _selectbox(app: AppTest, key: str):
    return next(widget for widget in app.selectbox if widget.key == key)


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
