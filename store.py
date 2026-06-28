import json
import os

import redis

# Конфигурация через env (см. docker-compose.yml).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAPPING_TTL_SECONDS = int(os.getenv("MAPPING_TTL_SECONDS", "3600"))

_KEY_PREFIX = "pii:mapping:"


class MappingStore:
    """Хранилище мэппингов анонимизации {тег: оригинал} в Redis по ID.

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
