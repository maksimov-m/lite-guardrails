import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.entrypoints.admin import router as admin_router
from src.adapters.db import get_version, init_db
from src.engine import GuardEngine
from src.runlog import RunLogger
from src.adapters.store import MappingStore

MAX_BATCH = 1000
_VERSION_POLL_SECONDS = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()                          # создать таблицы + засеять правила
    app.state.guard = GuardEngine()    # собрать детекторы из БД
    app.state.store = MappingStore()
    app.state.runlog = RunLogger()     # фоновое батч-логирование прогонов
    app.state.runlog.start()
    poller = asyncio.create_task(_version_poller(app))
    yield
    poller.cancel()
    await app.state.runlog.stop()      # дописать остаток очереди


async def _version_poller(app: FastAPI):
    """Фоново сверяет версию конфига; при смене (нажали Apply) — reload."""
    while True:
        await asyncio.sleep(_VERSION_POLL_SECONDS)
        try:
            if get_version() != app.state.guard.version:
                app.state.guard.reload()
        except Exception:
            pass  # не роняем поллер на временной ошибке БД


app = FastAPI(title="lite-guardrails", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.include_router(admin_router)


# --- модели ----------------------------------------------------------------
class TextIn(BaseModel):
    text: str = Field(..., examples=["привет, как дела?"])
    # произвольные метаданные запроса; пишутся в лог и доступны для фильтрации
    metadata: dict | None = Field(
        default=None, examples=[{"user_id": "42", "app": "support-bot"}])


class BatchIn(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=MAX_BATCH)


class DeanonymizeIn(BaseModel):
    id: str
    text: str


# --- helper: детекция + лог прогона ----------------------------------------
def _run(request: Request, module: str, text: str,
         metadata: dict | None = None) -> dict:
    guard = request.app.state.guard
    t0 = time.perf_counter()
    result = guard.detect(module, text)
    duration_ms = (time.perf_counter() - t0) * 1000
    # неблокирующая постановка лога в очередь; запись в БД — фоном пачками
    request.app.state.runlog.log(
        module=module, input_text=text,
        output=json.dumps(result, ensure_ascii=False),
        duration_ms=duration_ms, meta=metadata,
    )
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- детекторы -------------------------------------------------------------
@app.post("/detect/{module}", tags=["detectors"])
async def detect(module: str, body: TextIn, request: Request):
    if module not in ("pii", "nsfw", "relevant"):
        raise HTTPException(404, "unknown module")
    return _run(request, module, body.text, body.metadata)


@app.post("/detect/{module}/batch", tags=["batch"])
async def detect_batch(module: str, body: BatchIn, request: Request):
    if module not in ("pii", "nsfw", "relevant"):
        raise HTTPException(404, "unknown module")
    guard = request.app.state.guard
    return {"results": [guard.detect(module, t) for t in body.texts]}


# --- анонимизация PII ------------------------------------------------------
@app.post("/anonymize", tags=["pii"])
async def anonymize(body: TextIn, request: Request):
    text, mapping = request.app.state.guard.pii.anonymize(body.text)
    mapping_id = uuid.uuid4().hex
    if mapping:
        request.app.state.store.save(mapping_id, mapping)
    return {"id": mapping_id, "text": text}


@app.post("/deanonymize", tags=["pii"])
async def deanonymize(body: DeanonymizeIn, request: Request):
    mapping = request.app.state.store.get(body.id)
    if mapping is None:
        raise HTTPException(404, "mapping not found (неизвестный id или истёк TTL)")
    return {"text": request.app.state.guard.pii.deanonymize(body.text, mapping)}
