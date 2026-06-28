import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.db import get_version, init_db
from src.adapters.store import MappingStore
from src.engine import GuardEngine
from src.entrypoints.admin import router as admin_router
from src.entrypoints.nsfw import router as nsfw_router
from src.entrypoints.pii import router as pii_router
from src.entrypoints.relevant import router as relevant_router
from src.runlog import RunLogger

_VERSION_POLL_SECONDS = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.guard = GuardEngine()
    app.state.store = MappingStore()
    app.state.runlog = RunLogger()
    app.state.runlog.start()
    poller = asyncio.create_task(_version_poller(app))
    yield
    poller.cancel()
    await app.state.runlog.stop()


async def _version_poller(app: FastAPI):
    while True:
        await asyncio.sleep(_VERSION_POLL_SECONDS)
        try:
            if get_version() != app.state.guard.version:
                app.state.guard.reload()
        except Exception:
            pass


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


app.include_router(pii_router)
app.include_router(nsfw_router)
app.include_router(relevant_router)
app.include_router(admin_router)
