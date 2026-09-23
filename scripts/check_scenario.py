"""Run the main Akim scenario without an API key.

Usage: python scripts/check_scenario.py
"""

import os
import sys
from pathlib import Path

os.environ["AKIM_NO_LLM"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import akim  # noqa: E402


EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]
OVER_BUDGET = [
    {"measure": "M3", "district": "Нура"},
    {"measure": "M13", "district": "Байконур"},
    {"measure": "M7", "district": "Есиль"},
    {"measure": "M5", "district": "Алматы"},
    {"measure": "M6", "district": None},
]


def check(label, action, expected):
    try:
        actual = action()
        ok = actual == expected
        print(f"{'✓' if ok else '✗'} {label}: получил {actual!r}; ожидал {expected!r}")
        return ok
    except Exception as exc:
        print(f"✗ {label}: {type(exc).__name__}: {exc}")
        return False


def rejects_invalid_approval():
    try:
        akim.approve(EXAMPLE[:4])
    except ValueError:
        return True
    return False


def main():
    checks = [
        check("Данные: бюджет 100, 5 районов, 5 направлений", lambda: (
            akim.load_data()["budget"], len(akim.load_data()["districts"]),
            len(akim.load_data()["directions"])
        ), (100, 5, 5)),
        check("База", lambda: akim.baseline()["score"], 52.56),
        check("Набор дороже 100 отклонён", lambda: (
            not akim.evaluate(OVER_BUDGET)["valid"]
            and "budget" in [e["code"] for e in akim.evaluate(OVER_BUDGET)["errors"]]
        ), True),
        check("Пример организаторов", lambda: akim.evaluate(EXAMPLE)["score"], 56.54),
        check("Разбор без ключа: сильные стороны, риски, последствия", lambda: (
            (r := akim.explain(EXAMPLE))["mode"] == "template"
            and all(r[field] for field in ("strengths", "risks", "consequences"))
        ), True),
        check("Улучшить", lambda: akim.improve(EXAMPLE)["best"]["score"], 57.21),
        check("Лучший набор", lambda: akim.top(1)[0]["score"], 57.24),
        check("Недопустимый набор нельзя утвердить", rejects_invalid_approval, True),
    ]

    try:
        request = akim.parse_request("не ухудшай воздух в Сарыарке", EXAMPLE)
        mission = akim.run_mission(EXAMPLE, request)
        checks.append(check("Поручение: не ухудшай воздух в Сарыарке",
                            lambda: mission["recommendation"]["score"], 56.78))
        checks.append(check("Цена условий", lambda: mission["price"], 0.46))
        checks.append(check("Проверяющий сработал дважды", lambda: sum(
            step["role"] == "Проверяющий" for step in mission["steps"]
        ), 2))
    except Exception as exc:
        print(f"✗ Поручение: {type(exc).__name__}: {exc}")
        checks.extend([False, False, False])

    print(f"Итог: {sum(checks)}/{len(checks)} проверок")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
