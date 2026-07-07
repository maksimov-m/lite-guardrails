"""API-ключи клиентов детекшн-ручек."""

from fastapi import APIRouter, HTTPException, Request

from backend.entrypoints.admin.schemas import ApiKeyIn, ApiKeyPatch
from backend.entrypoints.admin.utils import db, key_out, refresh_keys
from backend.entrypoints.detectors.auth import generate_api_key

router = APIRouter()


@router.get("/api-keys")
def list_api_keys(request: Request, limit: int = 50, offset: int = 0):
    # Берём на одну строку больше запрошенного — так узнаём, есть ли ещё страница,
    # без отдельного COUNT(*). Пагинация на уровне SQL (LIMIT/OFFSET).
    rows = db(request).api_keys.list_page(limit + 1, offset)
    has_more = len(rows) > limit
    return {
        "keys": [key_out(k) for k in rows[:limit]],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@router.post("/api-keys")
def create_api_key(body: ApiKeyIn, request: Request):
    raw, key_hash, prefix = generate_api_key()
    row = db(request).api_keys.create(
        name=body.name,
        key_hash=key_hash,
        prefix=prefix,
        enabled=True,
        rate_limit_per_min=body.rate_limit_per_min,
    )
    refresh_keys(request)
    # Полный ключ показываем единственный раз — сохранить негде, хранится только хэш.
    return {**key_out(row), "key": raw}


@router.patch("/api-keys/{key_id}")
def update_api_key(key_id: int, body: ApiKeyPatch, request: Request):
    row = db(request).api_keys.update(key_id, body.model_dump())
    if not row:
        raise HTTPException(404, "api key not found")
    refresh_keys(request)
    return key_out(row)


@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, request: Request):
    if not db(request).api_keys.delete(key_id):
        raise HTTPException(404, "api key not found")
    refresh_keys(request)
    return {"deleted": key_id}
