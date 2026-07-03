"""Синхронный клиент lite-guardrails поверх httpx.

Берёт на себя: подстановку X-API-Key, таймауты, ретраи на сетевые/5xx ошибки,
разбор 401/429 в типизированные исключения. Публичный контракт — /v1.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

import httpx

from .errors import APIError, AuthError, RateLimitError


class GuardrailsClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ):
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> "GuardrailsClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # --- детекция ---
    def detect_pii(self, text: str, metadata: dict | None = None) -> dict:
        return self._post("/v1/detect/pii", _body(text, metadata))

    def detect_nsfw(self, text: str, metadata: dict | None = None) -> dict:
        return self._post("/v1/detect/nsfw", _body(text, metadata))

    def detect_relevant(self, text: str, metadata: dict | None = None) -> dict:
        return self._post("/v1/detect/relevant", _body(text, metadata))

    def detect_pii_batch(self, texts: Iterable[str]) -> Any:
        return self._post("/v1/detect/pii/batch", {"texts": list(texts)})

    def detect_nsfw_batch(self, texts: Iterable[str]) -> Any:
        return self._post("/v1/detect/nsfw/batch", {"texts": list(texts)})

    def detect_relevant_batch(self, texts: Iterable[str]) -> Any:
        return self._post("/v1/detect/relevant/batch", {"texts": list(texts)})

    # --- анонимизация ---
    def anonymize(self, text: str, deanonymize: bool = False) -> dict:
        """deanonymize=True — сохранить mapping в Redis (вернётся id), чтобы потом
        восстановить текст. По умолчанию False: Redis не используется, id=null.
        При True и недоступном Redis сервис вернёт 503 (-> APIError)."""
        return self._post("/v1/anonymize", {"text": text, "deanonymize": deanonymize})

    def anonymize_batch(self, texts: Iterable[str], deanonymize: bool = False) -> Any:
        return self._post("/v1/anonymize/batch", {"texts": list(texts), "deanonymize": deanonymize})

    def deanonymize(self, mapping_id: str, text: str) -> dict:
        return self._post("/v1/deanonymize", {"id": mapping_id, "text": text})

    # --- транспорт ---
    def _post(self, path: str, payload: dict) -> Any:
        for attempt in range(self._max_retries + 1):
            last = attempt == self._max_retries
            try:
                r = self._client.post(path, json=payload)
            except httpx.TransportError as e:
                if last:
                    raise APIError(f"transport error: {e}") from e
                time.sleep(0.2 * (attempt + 1))
                continue

            if r.status_code == 401:
                raise AuthError("невалидный или отсутствующий API-ключ")
            if r.status_code == 429:
                raise RateLimitError(
                    "превышен лимит запросов",
                    retry_after=int(r.headers.get("Retry-After", 0) or 0),
                )
            if r.status_code >= 500 and not last:
                time.sleep(0.2 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise APIError(f"{r.status_code}: {_detail(r)}", status_code=r.status_code)
            return r.json()


def _body(text: str, metadata: dict | None) -> dict:
    return {"text": text, "metadata": metadata} if metadata else {"text": text}


def _detail(r: httpx.Response) -> str:
    try:
        return r.json().get("detail", r.reason_phrase)
    except Exception:
        return r.reason_phrase
