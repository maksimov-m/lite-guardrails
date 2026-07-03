from abc import ABC, abstractmethod
from typing import NamedTuple


class RateLimitResult(NamedTuple):
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # секунд до сброса окна


class RateLimiter(ABC):
    """Порт ограничителя частоты запросов.

    Реализация решает, где хранить счётчики (Redis — общий на все воркеры,
    in-memory — для тестов). Меняем бэкенд — новый подкласс.
    """

    @abstractmethod
    def hit(self, identity: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Учесть один запрос от identity и сказать, укладывается ли он в limit
        за окно window_seconds."""
