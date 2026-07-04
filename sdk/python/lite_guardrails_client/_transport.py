"""Общая логика транспорта для sync/async клиентов.

Единый источник правды по: формированию тела запроса, разбору detail из ошибки
и лестнице статус-кодов (401/429/5xx/прочие 4xx). Sync- и async-клиенты
отличаются только тем, как они спят между ретраями (time.sleep vs asyncio.sleep)
и вызывают ли post с await — сама классификация ответа здесь одна на двоих.
"""

from __future__ import annotations

import httpx

from .errors import APIError, AuthError, RateLimitError

# Задержка перед ретраем растёт линейно: BASE * (номер попытки + 1).
RETRY_BASE_DELAY = 0.2


def build_body(text: str, metadata: dict | None) -> dict:
    return {"text": text, "metadata": metadata} if metadata else {"text": text}


def retry_delay(attempt: int) -> float:
    return RETRY_BASE_DELAY * (attempt + 1)


def classify_response(r: httpx.Response, *, last: bool) -> bool:
    """Классифицирует ответ на терминальный/повторяемый.

    Возвращает True, если запрос нужно повторить (5xx и попытки ещё есть).
    Бросает типизированную ошибку на 401/429 и на прочие ответы >= 400.
    На успешном ответе возвращает False (повтор не нужен, тело читает вызывающий).
    """
    if r.status_code == 401:
        raise AuthError("невалидный или отсутствующий API-ключ")
    if r.status_code == 429:
        raise RateLimitError(
            "превышен лимит запросов",
            retry_after=int(r.headers.get("Retry-After", 0) or 0),
        )
    if r.status_code >= 500 and not last:
        return True
    if r.status_code >= 400:
        raise APIError(f"{r.status_code}: {_detail(r)}", status_code=r.status_code)
    return False


def _detail(r: httpx.Response) -> str:
    try:
        return r.json().get("detail", r.reason_phrase)
    except Exception:
        return r.reason_phrase
