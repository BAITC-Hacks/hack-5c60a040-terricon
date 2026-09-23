"""Экран «Аким на 5 часов»: сервер для web/index.html.

Сервер ничего не считает сам: каждый ответ — функция движка akim; тексты для человека переводятся в простые слова.
Запуск из корня проекта: python web/server.py → http://localhost:8501 (HOST и PORT — из окружения).
"""

import json
import logging
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(os.getenv("AKIM_REPO") or ROOT.parent)))

import akim  # noqa: E402
from akim import llm  # noqa: E402

log = logging.getLogger("akim.web")

EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]
MEASURES = {measure["id"]: measure for measure in akim.load_data()["measures"]}
PLAIN_WORDS = [
    ("Сняты критические значения", "Решены острые проблемы"), ("критические значения", "острые проблемы"),
    ("критическое значение", "острая проблема"), ("На границе штрафа", "На грани острой проблемы"),
    ("сняты критические показатели", "решены острые проблемы"), ("критических показателей", "острых проблем"),
    ("критические показатели", "острые проблемы"),
    ("Сработала синергия", "Решения усилили друг друга:"), ("синергия", "усиление решений"),
    ("Расчёт Score", "Расчёт индекса"), ("Score города", "Индекс города"), ("к Score", "к индексу"),
    ("Score", "индекс"),
]
AUDIO_EXTENSIONS = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/x-wav": "wav",
                    "audio/mp4": "m4a", "audio/mpeg": "mp3"}
MAX_BODY = 8192
MAX_AUDIO = 10 * 1024 * 1024


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


def plain(text) -> str:
    """Тексты движка и модели — простыми словами: без «Score», «лаг», кодов мер; числа с запятой, даты не трогаем."""
    text = re.sub(r"лаг (\d+) кв\.", lambda match: quarters(int(match.group(1))), str(text or ""))
    text = re.sub(r"\bM\d{1,2}\s+(?=«)", "", text)  # «M3 «Линия ЛРТ»» — код перед названием не нужен
    text = re.sub(r"\bM\d{1,2}\b", lambda match: f"«{MEASURES[match.group(0)]['name']}»"
                  if match.group(0) in MEASURES else match.group(0), text)
    text = re.sub(r"(?<![\d.])(\d+)\.(\d{1,2})(?!\d|\.\d)", r"\1,\2", text)
    for old, new in PLAIN_WORDS:
        text = text.replace(old, new)
    return text


def words(plan: list[dict]) -> str:
    return "; ".join(f"{MEASURES[item['measure']]['name']} — {item.get('district') or 'весь город'}" for item in plan)


def name_of(item: dict | None) -> str:
    return f"{MEASURES[item['measure']]['name']} ({item.get('district') or 'весь город'})" if item else ""


def swap_names(swap: dict | None) -> dict | None:
    if swap:
        swap.update(replace_name=name_of(swap.get("replace")), with_name=name_of(swap.get("with")))
    return swap


def plain_mission(mission: dict | None) -> dict | None:
    if not mission:
        return mission
    mission["constraints"] = [plain(item) for item in mission.get("constraints", [])]
    mission["steps"] = [{**step, "action": plain(step["action"]), "result": plain(step["result"])}
                        for step in mission.get("steps", [])]
    mission["warnings"] = [plain(item) for item in mission.get("warnings", [])]
    mission["text"] = plain(mission.get("text"))
    if mission.get("recommendation"):
        mission["recommendation"]["words"] = words(mission["recommendation"]["plan"])
    return mission


def plan_of(body: dict) -> list[dict]:
    plan = body.get("plan")
    if not isinstance(plan, list):
        raise ValueError("Нужен набор решений")
    return plan


def initial() -> dict:
    return {"data": akim.load_data(), "base": akim.baseline(), "plan": EXAMPLE, "result": evaluate({"plan": EXAMPLE}),
            "best": akim.top(1)[0], "events": [{k: e[k] for k in ("id", "name", "description")} for e in akim.events()],
            "total": akim.total(), "model": llm.enabled()}


def evaluate(body: dict) -> dict:
    result = akim.evaluate(plan_of(body))
    for error in result.get("errors", []):
        error["message"] = plain(error["message"])
    return result


def explain(body: dict) -> dict:
    answer = akim.explain(plan_of(body))
    for key in ("strengths", "risks", "consequences"):
        answer[key] = [plain(item) for item in answer.get(key, [])]
    answer["text"] = plain(answer.get("text"))
    return answer


def improve(body: dict) -> dict:
    result = akim.improve(plan_of(body))
    swap_names(result.get("best"))
    return result


def mission(body: dict) -> dict:
    plan = plan_of(body)
    text = str(body.get("text") or "").strip() or "Улучши, но не ухудшай качество воздуха в Сарыарке"
    return plain_mission(akim.run_mission(plan, akim.parse_request(text, plan)))


def chat(body: dict) -> dict:
    history = [{"role": turn.get("role"), "content": str(turn.get("content", ""))}
               for turn in body.get("history") or [] if isinstance(turn, dict)]
    answer = akim.chat(str(body.get("message") or ""), plan_of(body), history)
    answer["reply"] = plain(answer.get("reply"))
    answer["tools_used"] = [plain(tool) for tool in answer.get("tools_used") or []]
    if answer.get("note"):
        answer["note"] = plain(answer["note"])
    plain_mission(answer.get("mission"))
    return answer


def stress(body: dict) -> dict:
    result = akim.stress_test(plan_of(body), str(body.get("event_id") or ""))
    result["event"] = {"id": result["event"]["id"], "name": result["event"]["name"]}
    result["text"] = plain(result.get("text"))
    swap_names(result.get("advice"))
    return result


def robust(body: dict) -> dict:
    result = akim.robustness(plan_of(body))
    for key in ("yours", "best", "robust"):
        if result.get(key):
            result[key]["words"] = words(result[key]["plan"])
    return result


def district(body: dict) -> dict:
    report = akim.district_report(str(body.get("district") or ""), plan_of(body))
    report["profile"] = plain(report.get("profile"))
    return report


def compare(body: dict) -> dict:
    plan_a, plan_b = body.get("plan_a"), body.get("plan_b")
    if not isinstance(plan_a, list) or not isinstance(plan_b, list):
        raise ValueError("Нужны два набора: сохранённый и текущий")
    result = akim.compare(plan_a, plan_b)
    result["only_in_a_words"] = words(result.get("only_in_a") or [])
    result["only_in_b_words"] = words(result.get("only_in_b") or [])
    return result


def rank(body: dict) -> dict:
    return akim.rank(plan_of(body)) or {}


def find(body: dict) -> list:
    return akim.find_best(max_budget=float(body.get("max_budget") or 100), include=body.get("include") or (),
                          exclude=body.get("exclude") or (), min_district_d=body.get("min_district_d") or None, n=5)


def approve(body: dict) -> dict:
    return akim.approve(plan_of(body))


def brief(body: dict) -> dict:
    return {"filename": "pasport_scenariya.md", "markdown": akim.brief(plan_of(body))}


def submit(body: dict) -> dict:
    akim.submit(str(body.get("team") or ""), plan_of(body))
    return {"ok": True}


GET = {
    "/api/health": lambda: {"ok": True},
    "/api/initial": initial,
    "/api/top": lambda: akim.top(5),
    "/api/frontier": akim.frontier,
    "/api/approved": akim.approved,
    "/api/leaderboard": akim.leaderboard,
}
POST = {
    "/api/evaluate": evaluate, "/api/explain": explain, "/api/improve": improve, "/api/mission": mission,
    "/api/chat": chat, "/api/stress": stress, "/api/robust": robust, "/api/district": district,
    "/api/rank": rank, "/api/find": find, "/api/compare": compare, "/api/sensitivity": lambda body: akim.sensitivity(plan_of(body)),
    "/api/approve": approve, "/api/brief": brief, "/api/submit": submit,
}


def _json_default(value):
    return value.item() if hasattr(value, "item") else str(value)


class Handler(BaseHTTPRequestHandler):
    def respond(self, body, content_type="application/json; charset=utf-8", status=200):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False,
                                                              default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def run(self, action):
        try:
            self.respond(action())
        except (ValueError, TypeError, KeyError, RuntimeError) as error:
            self.respond({"error": plain(str(error))}, status=400)
        except Exception:  # экран должен получить понятный ответ, причина — в журнале сервера
            log.exception("Ошибка обработки %s", self.path)
            self.respond({"error": "Внутренняя ошибка — попробуйте ещё раз"}, status=500)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.respond((ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/favicon.ico":
            return self.respond(b"", "image/x-icon", 204)
        if self.path in GET:
            return self.run(GET[self.path])
        self.respond({"error": "Не найдено"}, status=404)

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0") or 0)
        if self.path == "/api/transcribe":
            if not 0 < size <= MAX_AUDIO:
                return self.respond({"error": "Запись пустая или слишком длинная"}, status=400)
            audio = self.rfile.read(size)
            # OpenAI узнаёт формат по расширению имени: запись браузера — webm, а не wav
            kind = (self.headers.get("Content-Type") or "audio/webm").split(";")[0].strip().lower()
            filename = "voice." + AUDIO_EXTENSIONS.get(kind, "webm")
            return self.run(lambda: {"text": akim.transcribe(audio, filename=filename)})
        if self.path not in POST:
            return self.respond({"error": "Не найдено"}, status=404)
        if not 0 < size <= MAX_BODY:
            return self.respond({"error": "Неверный размер запроса"}, status=400)
        try:
            body = json.loads(self.rfile.read(size))
        except json.JSONDecodeError:
            return self.respond({"error": "Запрос не в формате JSON"}, status=400)
        self.run(lambda: POST[self.path](body if isinstance(body, dict) else {}))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8501"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Аким на 5 часов: http://localhost:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
