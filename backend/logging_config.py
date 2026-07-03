"""Настройка логирования приложения (stdout) и сквозной request-id.

Практики:
  - один обработчик на root, вывод в stdout — контейнер/ELK/Loki собирают сами;
  - structured JSON (одна строка = один объект) либо читаемый текст для локалки;
  - request-id на каждый запрос (из заголовка X-Request-ID или генерируем),
    попадает в каждую строку лога и в ответ — для корреляции;
  - PII не логируем: пишем метаданные запроса (метод, путь, статус, длительность,
    имя ключа), но никогда не тело/текст пользователя.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.requests import Request

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Пробы и метрики скрейпятся постоянно — не засоряем ими access-лог.
_SILENT_PATHS = {"/live", "/ready", "/health", "/metrics"}

_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}

access_log = logging.getLogger("access")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key != "request_id":
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str, json_output: bool) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    if json_output:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
        ))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


def install_request_logging(app) -> None:
    """Middleware: проставляет request-id и пишет один access-лог на запрос."""

    @app.middleware("http")
    async def _request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            if request.url.path not in _SILENT_PATHS:
                info = getattr(request.state, "api_key", None)
                access_log.info("request", extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    "api_key": info.get("name") if info else None,
                })
            return response
        finally:
            request_id_var.reset(token)
