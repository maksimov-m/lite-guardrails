import datetime as dt
from abc import ABC, abstractmethod
from typing import Any


class RunLogRepository(ABC):
    """Порт хранилища логов прогонов детекции.

    Отдельный порт: писать пачки логов и читать их под фильтры — самостоятельная
    задача (горячая запись из фонового воркера + чтение в админке), не связанная
    с CRUD конфига. Другой бэкенд логов — новый подкласс.

    Возвращаемые логи — объекты с атрибутами: .id, .created_at, .module,
    .input_text, .output, .duration_ms, .meta.
    """

    @abstractmethod
    def write_run_logs(self, batch: list[dict]) -> None:
        """Записать пачку логов (ключи dict совпадают с полями лога)."""

    @abstractmethod
    def query_run_logs(
        self,
        module: str | None = None,
        limit: int = 100,
        meta_key: str | None = None,
        meta_value: str | None = None,
    ) -> list[Any]:
        """Последние логи (новые сверху) под опциональными фильтрами."""

    @abstractmethod
    def run_log_meta_keys(self) -> list[str]:
        """Все встречающиеся в логах ключи metadata (для фильтра в UI)."""

    @abstractmethod
    def run_log_stats(self, since: dt.datetime, bucket_seconds: int) -> dict:
        """Агрегаты по логам с момента `since` (для дашборда). Формат:

        {
          "modules":  [{"module", "runs", "detections", "avg_ms", "p95_ms"}],
          "timeline": [{"ts": iso-строка начала бакета, "runs", "detections"}],
          "top_keys": [{"name", "runs"}],           # по meta.api_key
          "pii_classes": [{"class", "count"}],       # какие сущности ловит PII
        }

        Детекция = гуард сработал: для pii/nsfw — флаг <MODULE>_DETECT == true,
        для relevant — RELEVANT == false (пойман чит-чат/нерелевантное).
        """
