"""Админ-API: один parent-роутер с общим префиксом /admin и авторизацией
по X-Admin-Token. Сами эндпоинты — в routers/ по ресурсам; вспомогательная
логика — в utils.py."""

from fastapi import APIRouter, Depends

from backend.entrypoints.admin.routers import (
    api_keys,
    nsfw,
    observability,
    pii,
    relevant,
)
from backend.entrypoints.admin.utils import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

router.include_router(pii.router)
router.include_router(nsfw.router)
router.include_router(relevant.router)
router.include_router(api_keys.router)
router.include_router(observability.router)
