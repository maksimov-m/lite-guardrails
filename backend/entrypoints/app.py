import asyncio
import datetime as dt
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.db import SqlDatabase
from backend.adapters.rate_limit import RedisRateLimiter
from backend.adapters.store import RedisMappingStore
from backend.config import settings
from backend.engine import GuardEngine
from backend.entrypoints.admin import router as admin_router
from backend.entrypoints.detectors.auth import load_api_keys, require_api_key
from backend.entrypoints.detectors.nsfw import router as nsfw_router
from backend.entrypoints.detectors.pii import router as pii_router
from backend.entrypoints.detectors.relevant import router as relevant_router
from backend.entrypoints.health import router as health_router
from backend.entrypoints.metrics import router as metrics_router
from backend.logging_config import configure_logging, install_request_logging
from backend.runlog import RunLogger

log = logging.getLogger("app")

_VERSION_POLL_SECONDS = 3
_LOG_CLEANUP_INTERVAL_SECONDS = 3600  # как часто прогонять retention-чистку

# Префикс версии публичного API. Версионируем ТОЛЬКО клиентский контракт
# (detect/anonymize/deanonymize) — чтобы ломающие изменения выходили как /v2, не
# трогая живущих клиентов. Инфраструктура (admin, metrics, пробы) — вне версии.
API_V1 = "/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level, settings.log_json)
    db = SqlDatabase()
    db.init()
    app.state.repo = db
    app.state.guard = GuardEngine(db.pii, 
                                  db.nsfw, 
                                  db.relevant, 
                                  db.version)
    app.state.store = RedisMappingStore()
    app.state.rate_limiter = RedisRateLimiter()
    app.state.api_keys = load_api_keys(db.api_keys)
    app.state.runlog = RunLogger(db.runlog)
    app.state.runlog.start()
    poller = asyncio.create_task(_version_poller(app))
    cleaner = asyncio.create_task(_log_cleaner(app))
    yield
    poller.cancel()
    cleaner.cancel()
    await app.state.runlog.stop()


async def _log_cleaner(app: FastAPI):
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


async def _version_poller(app: FastAPI):
    while True:
        await asyncio.sleep(_VERSION_POLL_SECONDS)
        try:
            if app.state.repo.version.get_version() != app.state.guard.version:
                app.state.guard.reload()
            app.state.api_keys = load_api_keys(app.state.repo.api_keys)
        except Exception:
            pass


def create_app(lifespan=None) -> FastAPI:
    """Собрать приложение: CORS, роутеры детекторов/админки, метрики и пробы
    (/live, /ready, /health). Состояние (app.state) наполняет lifespan в проде;
    в тестах — подставляется вручную, поэтому lifespan опционален (тогда DB/Redis
    не поднимаются)."""
    app = FastAPI(title="lite-guardrails", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_methods=settings.cors_allow_methods_list,
        allow_headers=settings.cors_allow_headers_list,
    )
    install_request_logging(app)

    detect_auth = [Depends(require_api_key)]
    app.include_router(pii_router, prefix=API_V1, dependencies=detect_auth)
    app.include_router(nsfw_router, prefix=API_V1, dependencies=detect_auth)
    app.include_router(relevant_router, prefix=API_V1, dependencies=detect_auth)
    app.include_router(admin_router)
    app.include_router(metrics_router)  # без auth: скрейп Prometheus, защита на ingress
    app.include_router(health_router)  # без auth: пробы оркестратора
    return app


app = create_app(lifespan=lifespan)
