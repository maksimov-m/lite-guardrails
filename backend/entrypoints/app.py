import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.db import SqlDatabase
from backend.adapters.store import RedisMappingStore
from backend.engine import GuardEngine
from backend.entrypoints.admin import router as admin_router
from backend.entrypoints.detectors.auth import load_api_keys, require_api_key
from backend.entrypoints.detectors.nsfw import router as nsfw_router
from backend.entrypoints.detectors.pii import router as pii_router
from backend.entrypoints.detectors.relevant import router as relevant_router
from backend.runlog import RunLogger

_VERSION_POLL_SECONDS = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SqlDatabase()
    db.init()
    app.state.repo = db
    app.state.guard = GuardEngine(db.pii, 
                                  db.nsfw, 
                                  db.relevant, 
                                  db.version)
    app.state.store = RedisMappingStore()
    app.state.api_keys = load_api_keys(db.api_keys)
    app.state.runlog = RunLogger(db.runlog)
    app.state.runlog.start()
    poller = asyncio.create_task(_version_poller(app))
    yield
    poller.cancel()
    await app.state.runlog.stop()


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
    """Собрать приложение: CORS, /health и роутеры. Состояние (app.state)
    наполняет lifespan в проде; в тестах — подставляется вручную, поэтому
    lifespan опционален (тогда DB/Redis не поднимаются)."""
    app = FastAPI(title="lite-guardrails", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    detect_auth = [Depends(require_api_key)]
    app.include_router(pii_router, dependencies=detect_auth)
    app.include_router(nsfw_router, dependencies=detect_auth)
    app.include_router(relevant_router, dependencies=detect_auth)
    app.include_router(admin_router)
    return app


app = create_app(lifespan=lifespan)
