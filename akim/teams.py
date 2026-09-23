"""Team submissions and a local leaderboard for the shared city scenario."""

import json
from datetime import datetime
from pathlib import Path

from .scoring import evaluate
from .search import rank

STORE = Path(__file__).resolve().parent.parent / "var" / "teams.json"


def _submissions() -> list[dict]:
    if not STORE.exists():
        return []
    return json.loads(STORE.read_text(encoding="utf-8"))


def submit(team: str, plan: list[dict]) -> dict:
    name = team.strip() if isinstance(team, str) else ""
    if not name:
        raise ValueError("Укажите имя команды.")

    result = evaluate(plan)
    if not result["valid"]:
        raise ValueError("Набор недопустим: " + "; ".join(error["message"] for error in result["errors"]))

    position = rank(plan)
    item = {
        "team": name,
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "score": result["score"],
        "delta": result["delta"],
        "rank": position["rank"],
        "total": position["total"],
        "budget_used": result["budget_used"],
        "weakest": result["min_district"],
        "plan": [{"measure": row["measure"], "district": row["district"]} for row in result["plan"]],
    }
    rows = [row for row in _submissions() if row["team"].casefold() != name.casefold()]
    rows.append(item)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def leaderboard() -> list[dict]:
    rows = sorted(_submissions(), key=lambda row: (-row["score"], row["submitted_at"], row["team"]))
    return [
        {
            "place": index,
            "team": row["team"],
            "score": row["score"],
            "delta": row["delta"],
            "rank": row["rank"],
            "budget_used": row["budget_used"],
            "weakest": row["weakest"],
            "submitted_at": row["submitted_at"],
        }
        for index, row in enumerate(rows, start=1)
    ]
