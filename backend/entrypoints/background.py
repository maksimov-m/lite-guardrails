"""Фоновые циклы приложения: не отвечают на запросы, а поддерживают состояние.

Вынесены из app.py, чтобы сборка приложения оставалась декларативной, а логика
периодических задач (ретеншн логов, горячая перезагрузка конфига) жила отдельно
и тестировалась независимо.
"""

import asyncio
import datetime as dt
import logging

from fastapi import FastAPI

from backend.config import settings
from backend.entrypoints.detectors.auth import load_api_keys

log = logging.getLogger("app")

_VERSION_POLL_SECONDS = 3
_LOG_CLEANUP_INTERVAL_SECONDS = 3600  # как часто прогонять retention-чистку


async def run_log_cleaner(app: FastAPI) -> None:
    """Периодически удаляет логи старше retention (комплаенс + рост таблицы).
    Блокирующий DELETE — в threadpool; координация воркеров — в самом репозитории."""
    if settings.log_retention_days <= 0:
        return
    window = dt.timedelta(days=settings.log_retention_days)
    while True:
        try:
            cutoff = dt.datetime.utcnow() - window
            deleted = await asyncio.to_thread(
                app.state.repo.runlog.delete_run_logs_before, cutoff
            )
            if deleted:
                log.info("run_logs retention cleanup",
                         extra={"deleted": deleted, "retention_days": settings.log_retention_days})
        except Exception:
            pass
        await asyncio.sleep(_LOG_CLEANUP_INTERVAL_SECONDS)


async def run_version_poller(app: FastAPI) -> None:
    """Следит за версией конфига в БД и горячо перезагружает движок и ключи."""
    while True:
        await asyncio.sleep(_VERSION_POLL_SECONDS)
        try:
            if app.state.repo.version.get_version() != app.state.guard.version:
                app.state.guard.reload()
            app.state.api_keys = load_api_keys(app.state.repo.api_keys)
        except Exception:
            pass


def start_background_tasks(app: FastAPI) -> list[asyncio.Task]:
    """Запустить фоновые циклы и вернуть их задачи (для отмены при остановке)."""
    return [
        asyncio.create_task(run_version_poller(app)),
        asyncio.create_task(run_log_cleaner(app)),
    ]
