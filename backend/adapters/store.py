import json

import redis

from backend.config import settings
from backend.ports.mapping_store import MappingStore

# Конфигурация централизована в backend/config.py (заполняется из env / .env).
REDIS_URL = settings.redis_url
MAPPING_TTL_SECONDS = settings.mapping_ttl_seconds

_KEY_PREFIX = "pii:mapping:"


class RedisMappingStore(MappingStore):
    """Реализация MappingStore на Redis.

    Это PII, поэтому записи живут с TTL и сами протухают (MAPPING_TTL_SECONDS).
    """

    def __init__(self, url: str = REDIS_URL, ttl: int = MAPPING_TTL_SECONDS):
        # decode_responses -> работаем со str, а не bytes
        self._redis = redis.from_url(url, decode_responses=True)
        self._ttl = ttl

    def save(self, mapping_id: str, mapping: dict) -> None:
        self._redis.set(
            _KEY_PREFIX + mapping_id,
            json.dumps(mapping, ensure_ascii=False),
            ex=self._ttl,
        )

    def get(self, mapping_id: str) -> dict | None:
        raw = self._redis.get(_KEY_PREFIX + mapping_id)
        return json.loads(raw) if raw else None


class InMemoryMappingStore(MappingStore):
    """Реализация MappingStore в памяти процесса (без TTL).

    Для тестов и локального запуска без Redis. Не переживает рестарт и не
    шарится между воркерами — в проде использовать RedisMappingStore.
    """

    def __init__(self):
        self._data: dict[str, dict] = {}

    def save(self, mapping_id: str, mapping: dict) -> None:
        self._data[mapping_id] = dict(mapping)

    def get(self, mapping_id: str) -> dict | None:
        value = self._data.get(mapping_id)
        return dict(value) if value is not None else None
