from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.db import SqlDatabase
from backend.adapters.rate_limit import RedisRateLimiter
from backend.adapters.store import RedisMappingStore
from backend.config import settings
from backend.engine import GuardEngine
from backend.entrypoints.admin import router as admin_router
from backend.entrypoints.background import start_background_tasks
from backend.entrypoints.detectors.auth import load_api_keys, require_api_key
from backend.entrypoints.detectors.nsfw import router as nsfw_router
from backend.entrypoints.detectors.pii import router as pii_router
from backend.entrypoints.detectors.relevant import router as relevant_router
from backend.entrypoints.health import router as health_router
from backend.entrypoints.metrics import router as metrics_router
from backend.logging_config import configure_logging, install_request_logging
from backend.runlog import RunLogger

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
    tasks = start_background_tasks(app)
    yield
    for task in tasks:
        task.cancel()
    await app.state.runlog.stop()


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
