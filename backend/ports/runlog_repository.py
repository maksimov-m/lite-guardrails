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
        offset: int = 0,
        meta_key: str | None = None,
        meta_value: str | None = None,
    ) -> list[Any]:
        """Логи (новые сверху) под опциональными фильтрами, с offset/limit."""

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

    @abstractmethod
    def delete_run_logs_before(self, cutoff: dt.datetime) -> int:
        """Удалить логи старше cutoff (retention). Возвращает число удалённых.
        Реализация может ничего не удалить, если чистку уже ведёт другой воркер."""

    @abstractmethod
    def run_log_metrics(self, since: dt.datetime) -> dict:
        """Лёгкие агрегаты для Prometheus (`/metrics`): только счётчики,
        без таймлайна/перцентилей — запрос дешёвый, годится под частый scrape.

        Формат:
        {
          "total": int,                                    # всего прогонов
          "modules": [{"module", "runs", "detections"}],   # по модулям
        }

        Детекция трактуется так же, как в run_log_stats (гуард сработал).
        """
