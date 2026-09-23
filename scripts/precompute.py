import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akim.optimizer import TOP_PLANS_PATH, precompute  # noqa: E402


def main():
    start = time.perf_counter()
    result = precompute()
    elapsed = time.perf_counter() - start

    with open(TOP_PLANS_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Время расчёта: {elapsed:.1f} с")
    print(f"Допустимых наборов: {result['count']}")
    print(f"Файл сохранён: {TOP_PLANS_PATH}")


if __name__ == "__main__":
    main()
