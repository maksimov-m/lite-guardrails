"""Авторизация детекшн-ручек по API-ключу.

Ключи выдаются в админке и хранятся в БД как sha256-хэши. На хот-пути проверка
идёт по in-memory словарю {hash: {id, name}} (см. app.state.api_keys), который
заполняется при старте и обновляется version-поллером — без обращения к БД на
каждый запрос.
"""

import hashlib
import secrets

from fastapi import Header, HTTPException, Request

API_KEY_PREFIX = "gk_"


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
        row.key_hash: {"id": row.id, "name": row.name}
        for row in repo.list()
        if row.enabled
    }


def require_api_key(request: Request, x_api_key: str = Header(default="")):
    """Dependency детекшн-роутеров: пускаем только с валидным X-API-Key.
    При успехе кладёт инфо о ключе в request.state.api_key (уходит в логи)."""
    keys = getattr(request.app.state, "api_keys", {})
    if x_api_key:
        info = keys.get(hash_key(x_api_key))
        if info is not None:
            request.state.api_key = info
            return
    raise HTTPException(401, "невалидный или отсутствующий API-ключ")
