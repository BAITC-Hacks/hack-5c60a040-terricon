"""Сервер экрана web/server.py: каждая ручка отдаёт ответ движка с эталонными числами, тексты — простыми словами."""

import importlib.util
import json
import re
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import akim
import akim.approvals
import akim.teams

HERE = Path(__file__).resolve().parents[1]
SERVER = next(path for path in (HERE / "web" / "server.py", HERE / "server.py") if path.exists())
EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]
JARGON = re.compile(r"Score|\bM\d{1,2}\b|лаг \d")


@pytest.fixture(scope="module")
def url():
    spec = importlib.util.spec_from_file_location("akim_web_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["akim_web_server"] = module
    spec.loader.exec_module(module)
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(autouse=True)
def no_model_and_temp_stores(monkeypatch, tmp_path):
    monkeypatch.setenv("AKIM_NO_LLM", "1")
    monkeypatch.setattr(akim.approvals, "STORE", tmp_path / "approved.json")
    monkeypatch.setattr(akim.teams, "STORE", tmp_path / "teams.json")


def call(url, path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_initial_and_rules(url):
    status, initial = call(url, "/api/initial")
    assert status == 200 and initial["base"]["score"] == 52.56 and initial["result"]["score"] == 56.54
    assert initial["total"] == 694395 and len(initial["events"]) == 4 and initial["best"]["score"] == 57.24
    assert call(url, "/api/health") == (200, {"ok": True})
    over = [dict(item) for item in EXAMPLE]
    over[3] = {"measure": "M13", "district": "Нура"}
    status, result = call(url, "/api/evaluate", {"plan": over})
    assert status == 200 and not result["valid"]
    assert [e["message"] for e in result["errors"]] == ["Бюджет превышен: 109 из 100"]
    status, duplicate = call(url, "/api/evaluate", {"plan": EXAMPLE[:4] + [EXAMPLE[0]]})
    assert "M7" not in " ".join(e["message"] for e in duplicate["errors"])


def test_agent_explain_improve_mission_chat(url):
    status, explanation = call(url, "/api/explain", {"plan": EXAMPLE})
    texts = explanation["strengths"] + explanation["risks"] + explanation["consequences"]
    assert status == 200 and explanation["mode"] == "template" and texts and not JARGON.search(" ".join(texts))
    status, better = call(url, "/api/improve", {"plan": EXAMPLE})
    assert better["best"]["score"] == 57.21 and "Линия ЛРТ" in better["best"]["with_name"]
    status, mission = call(url, "/api/mission", {"plan": EXAMPLE, "text": ""})
    assert mission["status"] == "ok" and mission["recommendation"]["score"] == 56.78 and mission["price"] == 0.46
    steps = " ".join(step["action"] + step["result"] for step in mission["steps"])
    assert "Проверяющий" in [step["role"] for step in mission["steps"]] and not JARGON.search(steps)
    status, answer = call(url, "/api/chat", {"plan": EXAMPLE, "message": "Почему такой результат?", "history": []})
    assert status == 200 and answer["reply"] and not JARGON.search(answer["reply"])
    status, ordered = call(url, "/api/chat", {"plan": EXAMPLE,
                                              "message": "Улучши, но не ухудшай качество воздуха в Сарыарке"})
    assert ordered["mission"]["recommendation"]["score"] == 56.78 and ordered["suggestion"]


def test_stress_robust_and_search(url):
    status, smog = call(url, "/api/stress", {"plan": EXAMPLE, "event_id": "smog"})
    assert status == 200 and smog["score_after"] == 55.3 and smog["event"]["name"] == "Зимний смог"
    improved = call(url, "/api/improve", {"plan": EXAMPLE})[1]["best"]["plan"]
    status, improved_smog = call(url, "/api/stress", {"plan": improved, "event_id": "smog"})
    assert (improved_smog["score_before"], improved_smog["score_after"]) == (57.21, 55.6)  # «Показ за 3 минуты», шаг 5
    status, robust = call(url, "/api/robust", {"plan": EXAMPLE})
    assert robust["robust"]["worst"] == 55.82 and robust["price"] == 0.17 and robust["yours"]["words"]
    status, top = call(url, "/api/top")
    assert len(top) == 5 and top[0]["score"] == 57.24
    status, found = call(url, "/api/find", {"max_budget": 80})
    assert found[0]["score"] == 56.87 and found[0]["cost"] <= 80
    status, district = call(url, "/api/district", {"plan": EXAMPLE, "district": "Нура"})
    assert district["d"] == 52.96 and district["place_from_bottom"] == 1
    assert call(url, "/api/rank", {"plan": EXAMPLE})[1]["rank"] == 566
    best = top[0]["plan"]
    status, compared = call(url, "/api/compare", {"plan_a": EXAMPLE, "plan_b": best})
    assert compared["a"]["score"] == 56.54 and compared["b"]["score"] == 57.24 and compared["score_diff"] == 0.7
    assert compared["only_in_a_words"] and len(compared["districts"]) == 5
    status, frontier = call(url, "/api/frontier")
    assert max(point["score"] for point in frontier) == 57.24
    assert call(url, "/api/stress", {"plan": EXAMPLE[:4], "event_id": "smog"})[0] == 400


def test_human_decision_brief_and_rating(url):
    status, approved = call(url, "/api/approve", {"plan": EXAMPLE})
    assert status == 200 and approved["score"] == 56.54
    assert call(url, "/api/approved")[1][-1]["score"] == 56.54
    assert call(url, "/api/approve", {"plan": EXAMPLE[:4]})[0] == 400
    status, brief = call(url, "/api/brief", {"plan": EXAMPLE})
    assert brief["filename"].endswith(".md") and "56,54" in brief["markdown"]
    assert call(url, "/api/submit", {"team": "Terricon", "plan": EXAMPLE}) == (200, {"ok": True})
    assert call(url, "/api/leaderboard")[1][0]["team"] == "Terricon"
    assert call(url, "/api/submit", {"team": "", "plan": EXAMPLE})[0] == 400


FEATURES = [
    "Вернуть пример", "Выбрать набор с максимальным индексом", "Получить разбор", "Найти улучшение",
    "Выполнить поручение", "Спросить агента", "Сказать голосом", "Проверить сценарий", "Найти самый устойчивый",
    "Утвердить", "Скачать паспорт сценария", "Отправить в рейтинг", "Показать 5 лучших", "Подобрать",
    "Проверить приоритеты", "Сохранить текущий как вариант A",
]


def test_page_has_every_feature_and_clean_text(url):
    with urllib.request.urlopen(url + "/", timeout=30) as response:
        page = response.read().decode("utf-8")
    missing = [label for label in FEATURES if label not in page]
    assert not missing, f"на экране нет: {missing}"
    assert not re.search(r"\?{4,}", page), "кириллица испорчена знаками «????»"
    assert "Альтернативный" not in page and "прототип" not in page


def test_plain_words_for_tool_names_numbers_and_codes(url):
    plain = sys.modules["akim_web_server"].plain
    assert plain("Расчёт Score") == "Расчёт индекса"
    assert plain("M3 «Линия ЛРТ / расширение» — Нура, Score 57.21") == "«Линия ЛРТ / расширение» — Нура, индекс 57,21"
    assert plain("утверждено 23.09.2026") == "утверждено 23.09.2026"


def test_every_api_call_of_the_page_exists_on_server(url):
    module = sys.modules["akim_web_server"]
    with urllib.request.urlopen(url + "/", timeout=30) as response:
        page = response.read().decode("utf-8")
    called = set(re.findall(r"/api/[a-z_]+", page))
    known = set(module.GET) | set(module.POST) | {"/api/transcribe"}
    assert called and called <= known, f"страница вызывает несуществующее: {sorted(called - known)}"


def test_voice_recording_from_browser_is_sent_as_webm(url, monkeypatch):
    # 23.09 живой вызов: запись браузера (webm) под именем voice.wav OpenAI отклоняет — «unsupported_format»
    seen = {}
    monkeypatch.setattr(akim, "transcribe", lambda audio, filename="voice.wav": seen.update(filename=filename) or "Что с Нурой?")
    request = urllib.request.Request(url + "/api/transcribe", data=b"webm", headers={"Content-Type": "audio/webm;codecs=opus"})
    with urllib.request.urlopen(request, timeout=30) as response:
        assert json.loads(response.read()) == {"text": "Что с Нурой?"}
    assert seen["filename"] == "voice.webm"


def test_voice_without_key_and_unknown_path(url):
    request = urllib.request.Request(url + "/api/transcribe", data=b"RIFF", headers={"Content-Type": "audio/wav"})
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=30)
    assert error.value.code == 400 and "ключ" in json.loads(error.value.read())["error"]
    assert call(url, "/api/nothing")[0] == 404
