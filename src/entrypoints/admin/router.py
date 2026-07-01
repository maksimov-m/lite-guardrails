import re
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from src.config import settings
from src.entrypoints.admin.schemas import (
    ApiKeyIn,
    ApiKeyPatch,
    NsfwDictIn,
    NsfwDictPatch,
    PiiRuleIn,
    PiiRulePatch,
    RelevantIn,
    RelevantPatch,
)
from src.entrypoints.detectors.auth import generate_api_key, load_api_keys

MAX_REGEX_LEN = 1000

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(x_admin_token: str = Header(default="")):
    # compare_digest — сравнение за постоянное время (защита от timing-атаки).
    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(401, "invalid admin token")


def _db(request: Request):
    return request.app.state.repo


def validate_regex(pattern: str):
    if len(pattern) > MAX_REGEX_LEN:
        raise HTTPException(400, f"regex слишком длинный (> {MAX_REGEX_LEN})")
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise HTTPException(400, f"невалидный regex: {e}") from e


def _autoapply(request: Request):
    """Авто-применение: bump версии + немедленный reload этого воркера."""
    _db(request).version.bump_version()
    request.app.state.guard.reload()


def _refresh_keys(request: Request):
    """Обновить кэш API-ключей на этом воркере сразу после правки.
    Остальные воркеры подхватят изменения на ближайшем тике поллера."""
    request.app.state.api_keys = load_api_keys(_db(request).api_keys)


# --- PII: regex-сигнатуры по типам -----------------------------------------
def _pii_out(r) -> dict:
    return {"id": r.id, "type": r.type, "regex": r.regex, "enabled": r.enabled}


@router.get("/pii", dependencies=[Depends(require_admin)])
def list_pii(request: Request):
    return {"rules": [_pii_out(r) for r in _db(request).pii.list()]}


@router.post("/pii", dependencies=[Depends(require_admin)])
def create_pii(body: PiiRuleIn, request: Request):
    validate_regex(body.regex)
    rule = _db(request).pii.create(type=body.type, 
                                   regex=body.regex, 
                                   enabled=body.enabled)
    _autoapply(request)
    return _pii_out(rule)


@router.patch("/pii/{rule_id}", dependencies=[Depends(require_admin)])
def update_pii(rule_id: int, body: PiiRulePatch, request: Request):
    if body.regex is not None:
        validate_regex(body.regex)
    rule = _db(request).pii.update(rule_id, body.model_dump())
    if not rule:
        raise HTTPException(404, "pii rule not found")
    _autoapply(request)
    return _pii_out(rule)


@router.delete("/pii/{rule_id}", dependencies=[Depends(require_admin)])
def delete_pii(rule_id: int, request: Request):
    if not _db(request).pii.delete(rule_id):
        raise HTTPException(404, "pii rule not found")
    _autoapply(request)
    return {"deleted": rule_id}


# --- NSFW: словари (имя + текст со словами) ---------------------------------
def _nsfw_out(d) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "enabled": d.enabled,
        "word_count": len(d.text.split()),
    }


@router.get("/nsfw", dependencies=[Depends(require_admin)])
def list_nsfw(request: Request):
    return {"dicts": [_nsfw_out(d) for d in _db(request).nsfw.list()]}


@router.get("/nsfw/{dict_id}", dependencies=[Depends(require_admin)])
def get_nsfw(dict_id: int, request: Request):
    """Полный словарь вместе с текстом слов — для редактирования в UI
    (в list текст намеренно не отдаём: встроенный словарь большой)."""
    dictionary = _db(request).nsfw.get(dict_id)
    if not dictionary:
        raise HTTPException(404, "dict not found")
    return {**_nsfw_out(dictionary), "text": dictionary.text}


@router.post("/nsfw", dependencies=[Depends(require_admin)])
def create_nsfw(body: NsfwDictIn, request: Request):
    nsfw = _db(request).nsfw
    if nsfw.find_by("name", body.name):
        raise HTTPException(400, "словарь с таким именем уже есть")
    dictionary = nsfw.create(name=body.name, text=body.text, enabled=True)
    _autoapply(request)
    return _nsfw_out(dictionary)


@router.patch("/nsfw/{dict_id}", dependencies=[Depends(require_admin)])
def update_nsfw(dict_id: int, body: NsfwDictPatch, request: Request):
    nsfw = _db(request).nsfw
    current = nsfw.get(dict_id)
    if not current:
        raise HTTPException(404, "dict not found")
    if body.name is not None and body.name != current.name and nsfw.find_by("name", body.name):
        raise HTTPException(400, "словарь с таким именем уже есть")
    dictionary = nsfw.update(dict_id, body.model_dump())
    _autoapply(request)
    return _nsfw_out(dictionary)


@router.get("/nsfw/{dict_id}/export", dependencies=[Depends(require_admin)])
def export_nsfw(dict_id: int, request: Request):
    dictionary = _db(request).nsfw.get(dict_id)
    if not dictionary:
        raise HTTPException(404, "dict not found")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", dictionary.name).strip("_") or "dict"
    return PlainTextResponse(
        dictionary.text,
        headers={"Content-Disposition": f'attachment; filename="{safe}.txt"'},
    )


@router.delete("/nsfw/{dict_id}", dependencies=[Depends(require_admin)])
def delete_nsfw(dict_id: int, request: Request):
    if not _db(request).nsfw.delete(dict_id):
        raise HTTPException(404, "dict not found")
    _autoapply(request)
    return {"deleted": dict_id}


# --- relevant: категории смолтока (тип + текст с фразами) -------------------
def _relevant_out(c) -> dict:
    return {"id": c.id, "type": c.type, "text": c.text, "enabled": c.enabled}


@router.get("/relevant", dependencies=[Depends(require_admin)])
def list_relevant(request: Request):
    return {"categories": [_relevant_out(c) for c in _db(request).relevant.list()]}


@router.post("/relevant", dependencies=[Depends(require_admin)])
def create_relevant(body: RelevantIn, request: Request):
    relevant = _db(request).relevant
    if relevant.find_by("type", body.type):
        raise HTTPException(400, "категория с таким типом уже есть")
    category = relevant.create(type=body.type, text=body.text, enabled=True)
    _autoapply(request)
    return _relevant_out(category)


@router.patch("/relevant/{cat_id}", dependencies=[Depends(require_admin)])
def update_relevant(cat_id: int, body: RelevantPatch, request: Request):
    relevant = _db(request).relevant
    current = relevant.get(cat_id)
    if not current:
        raise HTTPException(404, "category not found")
    if body.type is not None and body.type != current.type and relevant.find_by("type", body.type):
        raise HTTPException(400, "категория с таким типом уже есть")
    category = relevant.update(cat_id, body.model_dump())
    _autoapply(request)
    return _relevant_out(category)


@router.delete("/relevant/{cat_id}", dependencies=[Depends(require_admin)])
def delete_relevant(cat_id: int, request: Request):
    if not _db(request).relevant.delete(cat_id):
        raise HTTPException(404, "category not found")
    _autoapply(request)
    return {"deleted": cat_id}


@router.get("/version", dependencies=[Depends(require_admin)])
def version(request: Request):
    return {
        "db_version": _db(request).version.get_version(),
        "active_version": request.app.state.guard.version,
    }


# --- логи прогонов ---------------------------------------------------------
@router.get("/logs", dependencies=[Depends(require_admin)])
def logs(
    request: Request,
    module: str | None = None,
    limit: int = 100,
    meta_key: str | None = None,
    meta_value: str | None = None,
):
    rows = _db(request).runlog.query_run_logs(module, limit, meta_key, meta_value)
    return {
        "logs": [
            {
                "id": r.id,
                "ts": r.created_at.isoformat(),
                "module": r.module,
                "input": r.input_text,
                "output": r.output,
                "duration_ms": round(r.duration_ms, 3),
                "meta": r.meta,
            }
            for r in rows
        ]
    }


@router.get("/logs/meta-keys", dependencies=[Depends(require_admin)])
def logs_meta_keys(request: Request):
    """Список всех встречающихся в логах ключей metadata (для фильтра в UI)."""
    return {"keys": _db(request).runlog.run_log_meta_keys()}


# --- API-ключи клиентов ----------------------------------------------------
def _key_out(k) -> dict:
    """Безопасное представление: сам ключ не отдаём, только prefix."""
    return {
        "id": k.id,
        "name": k.name,
        "prefix": k.prefix,
        "enabled": k.enabled,
        "created_at": k.created_at.isoformat(),
    }


@router.get("/api-keys", dependencies=[Depends(require_admin)])
def list_api_keys(request: Request):
    return {"keys": [_key_out(k) for k in _db(request).api_keys.list()]}


@router.post("/api-keys", dependencies=[Depends(require_admin)])
def create_api_key(body: ApiKeyIn, request: Request):
    raw, key_hash, prefix = generate_api_key()
    row = _db(request).api_keys.create(
        name=body.name, key_hash=key_hash, prefix=prefix, enabled=True
    )
    _refresh_keys(request)
    # Полный ключ показываем единственный раз — сохранить негде, хранится только хэш.
    return {**_key_out(row), "key": raw}


@router.patch("/api-keys/{key_id}", dependencies=[Depends(require_admin)])
def update_api_key(key_id: int, body: ApiKeyPatch, request: Request):
    row = _db(request).api_keys.update(key_id, body.model_dump())
    if not row:
        raise HTTPException(404, "api key not found")
    _refresh_keys(request)
    return _key_out(row)


@router.delete("/api-keys/{key_id}", dependencies=[Depends(require_admin)])
def delete_api_key(key_id: int, request: Request):
    if not _db(request).api_keys.delete(key_id):
        raise HTTPException(404, "api key not found")
    _refresh_keys(request)
    return {"deleted": key_id}
