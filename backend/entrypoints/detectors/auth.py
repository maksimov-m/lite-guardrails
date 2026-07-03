"""Авторизация детекшн-ручек по API-ключу.

Ключи выдаются в админке и хранятся в БД как sha256-хэши. На хот-пути проверка
идёт по in-memory словарю {hash: {id, name}} (см. app.state.api_keys), который
заполняется при старте и обновляется version-поллером — без обращения к БД на
каждый запрос.
"""

import hashlib
import logging
import secrets

from fastapi import Header, HTTPException, Request, Response

from backend.config import settings

log = logging.getLogger("auth")

API_KEY_PREFIX = "gk_"
_RATE_WINDOW_SECONDS = 60


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Возвращает (полный_ключ, hash, prefix). Полный ключ нигде не хранится —
    его показывают вызывающему один раз."""
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_key(raw), raw[:12]


def load_api_keys(repo) -> dict[str, dict]:
    """Снимок включённых ключей из БД в словарь для быстрой проверки."""
    return {
        row.key_hash: {
            "id": row.id,
            "name": row.name,
            "rate_limit_per_min": getattr(row, "rate_limit_per_min", None),
        }
        for row in repo.list()
        if row.enabled
    }


def require_api_key(
    request: Request, response: Response, x_api_key: str = Header(default="")
):
    """Dependency детекшн-роутеров: валидный X-API-Key + лимит частоты.
    При успехе кладёт инфо о ключе в request.state.api_key (уходит в логи)."""
    keys = getattr(request.app.state, "api_keys", {})
    info = keys.get(hash_key(x_api_key)) if x_api_key else None
    if info is None:
        raise HTTPException(401, "невалидный или отсутствующий API-ключ")
    request.state.api_key = info
    _enforce_rate_limit(request, response, info)


def _enforce_rate_limit(request: Request, response: Response, info: dict) -> None:
    """Fixed-window лимит на ключ. Redis недоступен — fail-open (пускаем)."""
    per_key = info.get("rate_limit_per_min")
    limit = settings.rate_limit_default_per_min if per_key is None else per_key
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limit <= 0 or limiter is None:  # <=0 — без ограничения
        return
    try:
        r = limiter.hit(f"key:{info['id']}", limit, _RATE_WINDOW_SECONDS)
    except Exception:
        return
    response.headers["X-RateLimit-Limit"] = str(r.limit)
    response.headers["X-RateLimit-Remaining"] = str(r.remaining)
    if not r.allowed:
        log.warning("rate limit exceeded",
                    extra={"key_id": info["id"], "limit": r.limit})
        raise HTTPException(
            429,
            "превышен лимит запросов",
            headers={"Retry-After": str(r.retry_after),
                     "X-RateLimit-Limit": str(r.limit),
                     "X-RateLimit-Remaining": "0"},
        )
