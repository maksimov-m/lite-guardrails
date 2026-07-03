import time

import redis

from backend.config import settings
from backend.ports.rate_limiter import RateLimiter, RateLimitResult

# Атомарно: INCR + EXPIRE только на первом попадании в окно (иначе TTL сползал бы
# на каждом запросе и окно не закрывалось). Fixed-window — 1 round-trip на запрос.
_HIT_LUA = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return c
"""


def _result(count: int, limit: int, window_seconds: int, now: int) -> RateLimitResult:
    return RateLimitResult(
        allowed=count <= limit,
        limit=limit,
        remaining=max(0, limit - count),
        retry_after=window_seconds - (now % window_seconds),
    )


class RedisRateLimiter(RateLimiter):
    """Fixed-window счётчик в Redis: общий для всех воркеров, лимит точный."""

    def __init__(self, url: str = settings.redis_url):
        self._redis = redis.from_url(url)
        self._hit = self._redis.register_script(_HIT_LUA)

    def hit(self, identity: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        key = f"ratelimit:{identity}:{now // window_seconds}"
        count = int(self._hit(keys=[key], args=[window_seconds]))
        return _result(count, limit, window_seconds, now)


class InMemoryRateLimiter(RateLimiter):
    """Счётчик в памяти процесса (тесты/локальный запуск без Redis)."""

    def __init__(self):
        self._counts: dict[tuple[str, int], int] = {}

    def hit(self, identity: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        key = (identity, now // window_seconds)
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        return _result(count, limit, window_seconds, now)
