import logging
import os

from . import llm

log = logging.getLogger("akim.voice")


def transcribe(audio_bytes: bytes, filename: str = "voice.wav") -> str:
    if not llm.enabled():
        raise RuntimeError("Голос работает с ключом OpenAI: добавьте OPENAI_API_KEY в .env. Пока напишите текстом.")
    model = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")
    try:
        result = llm._client().audio.transcriptions.create(model=model, file=(filename, audio_bytes), language="ru")
    except Exception as exc:
        log.warning("Распознавание речи не удалось (%s): %s", model, exc)
        raise RuntimeError("Не удалось распознать речь — попробуйте ещё раз или напишите текстом.") from exc
    return result.text.strip()
