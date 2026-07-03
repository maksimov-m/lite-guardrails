import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.domain.detectors.errors import DetectorTimeout
from backend.logging_config import request_id_var

log = logging.getLogger("app")


async def _detector_timeout_handler(request: Request, exc: DetectorTimeout) -> JSONResponse:
    """Fail-closed: детектор не уложился в бюджет (вероятный ReDoS в правиле).
    Возвращаем 500 и НЕ логируем сырой ввод (это может быть PII или пейлоад атаки)
    — только имя правила и путь, чтобы операторы нашли и починили паттерн."""
    log.warning(
        "detector match timeout", extra={"pattern": exc.pattern_name, "path": request.url.path}
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "детекция не завершилась в срок; запрос отклонён"},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Единая точка логирования непойманных исключений: стектрейс в нашем JSON
    с request_id (иначе 500 логировал бы uvicorn своим форматом без корреляции).
    request_id достаём из request.state — http-middleware к этому моменту уже
    сбросил contextvar; восстанавливаем его на время записи лога."""
    rid = getattr(request.state, "request_id", None)
    if rid:
        request_id_var.set(rid)
    log.error(
        "unhandled exception",
        extra={"method": request.method, "path": request.url.path},
        exc_info=exc,
    )
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
