import logging
import os
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("akim.llm")
ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def enabled() -> bool:
    if os.getenv("AKIM_NO_LLM"):
        return False
    load_env()
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5.6-sol").strip()


def _is_reasoning(name: str) -> bool:
    return name.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4"))


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    return OpenAI(
        timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "1")),
    )


def complete(messages: list[dict], *, json_mode: bool = False, tools: list[dict] | None = None,
             model: str | None = None, max_completion_tokens: int | None = None,
             reasoning_effort: str | None = None):
    # temperature не передаём: у gpt-5.6-sol и gpt-6-astra вызов с ним падает
    name = (model or model_name()).strip()
    kwargs = {"model": name, "messages": messages}
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    elif _is_reasoning(name):
        # с инструментами Chat Completions принимает только reasoning_effort="none"
        kwargs["reasoning_effort"] = "none" if tools else os.getenv("OPENAI_REASONING_EFFORT", "low")
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if tools:
        kwargs["tools"] = tools
    if max_completion_tokens is not None:
        kwargs["max_completion_tokens"] = max_completion_tokens
    return _client().chat.completions.create(**kwargs)
