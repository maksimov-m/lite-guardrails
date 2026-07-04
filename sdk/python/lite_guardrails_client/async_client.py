"""Асинхронный клиент lite-guardrails поверх httpx.AsyncClient.

Полное зеркало синхронного GuardrailsClient: та же подстановка X-API-Key,
таймауты, ретраи на сетевые/5xx ошибки и разбор 401/429 в типизированные
исключения (общая логика — в _transport). Отличие только в await и в
асинхронном контекст-менеджере (`async with`).
"""

from __future__ import annotations

import asyncio
from typing import Any, Iterable

import httpx

from ._transport import build_body, classify_response, retry_delay
from .errors import APIError


class AsyncGuardrailsClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout,
            transport=transport,
        )

    async def __aenter__(self) -> "AsyncGuardrailsClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- детекция ---
    async def detect_pii(self, text: str, metadata: dict | None = None) -> dict:
        return await self._post("/v1/detect/pii", build_body(text, metadata))

    async def detect_nsfw(self, text: str, metadata: dict | None = None) -> dict:
        return await self._post("/v1/detect/nsfw", build_body(text, metadata))

    async def detect_relevant(self, text: str, metadata: dict | None = None) -> dict:
        return await self._post("/v1/detect/relevant", build_body(text, metadata))

    async def detect_pii_batch(self, texts: Iterable[str]) -> Any:
        return await self._post("/v1/detect/pii/batch", {"texts": list(texts)})

    async def detect_nsfw_batch(self, texts: Iterable[str]) -> Any:
        return await self._post("/v1/detect/nsfw/batch", {"texts": list(texts)})

    async def detect_relevant_batch(self, texts: Iterable[str]) -> Any:
        return await self._post("/v1/detect/relevant/batch", {"texts": list(texts)})

    # --- анонимизация ---
    async def anonymize(self, text: str, deanonymize: bool = False) -> dict:
        """deanonymize=True — сохранить mapping в Redis (вернётся id), чтобы потом
        восстановить текст. По умолчанию False: Redis не используется, id=null.
        При True и недоступном Redis сервис вернёт 503 (-> APIError)."""
        return await self._post("/v1/anonymize", {"text": text, "deanonymize": deanonymize})

    async def anonymize_batch(self, texts: Iterable[str], deanonymize: bool = False) -> Any:
        return await self._post(
            "/v1/anonymize/batch", {"texts": list(texts), "deanonymize": deanonymize}
        )

    async def deanonymize(self, mapping_id: str, text: str) -> dict:
        return await self._post("/v1/deanonymize", {"id": mapping_id, "text": text})

    # --- транспорт ---
    async def _post(self, path: str, payload: dict) -> Any:
        for attempt in range(self._max_retries + 1):
            last = attempt == self._max_retries
            try:
                r = await self._client.post(path, json=payload)
            except httpx.TransportError as e:
                if last:
                    raise APIError(f"transport error: {e}") from e
                await asyncio.sleep(retry_delay(attempt))
                continue

            if classify_response(r, last=last):
                await asyncio.sleep(retry_delay(attempt))
                continue
            return r.json()
