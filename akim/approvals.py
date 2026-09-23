import json
from datetime import datetime
from pathlib import Path

from .scoring import evaluate

STORE = Path(__file__).resolve().parent.parent / "var" / "approved.json"


def approved() -> list[dict]:
    if not STORE.exists():
        return []
    return json.loads(STORE.read_text(encoding="utf-8"))


def approve(plan: list[dict], note: str = "") -> dict:
    res = evaluate(plan)
    if not res["valid"]:
        raise ValueError("Набор недопустим: " + "; ".join(e["message"] for e in res["errors"]))
    item = {
        "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "score": res["score"],
        "delta": res["delta"],
        "budget_used": res["budget_used"],
        "plan": [{"measure": p["measure"], "district": p["district"], "name": p["name"]} for p in res["plan"]],
        "note": note,
    }
    items = approved() + [item]
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return item
