"""Relevant: категории смолтока (тип + текст с фразами)."""

from fastapi import APIRouter, HTTPException, Request

from backend.entrypoints.admin.schemas import RelevantIn, RelevantPatch, RelevantSettingsIn
from backend.entrypoints.admin.utils import bump_and_reload, db, relevant_out
from backend.runtime_settings import RELEVANT_GIBBERISH_ENABLED, get_bool, set_bool

router = APIRouter()


def _relevant_settings(request: Request) -> dict:
    store = db(request).settings
    return {"gibberish_enabled": get_bool(store, RELEVANT_GIBBERISH_ENABLED)}


@router.get("/relevant")
def list_relevant(request: Request):
    return {"categories": [relevant_out(c) for c in db(request).relevant.list()]}


# Настройки модуля (этапы детекции, не привязанные к строкам-категориям).
# Объявлены до /relevant/{cat_id}: путь "settings" не число, под int-конвертер
# всё равно не попадёт, но держим рядом для наглядности.
@router.get("/relevant/settings")
def get_relevant_settings(request: Request):
    return _relevant_settings(request)


@router.put("/relevant/settings")
def update_relevant_settings(body: RelevantSettingsIn, request: Request):
    store = db(request).settings
    if body.gibberish_enabled is not None:
        set_bool(store, RELEVANT_GIBBERISH_ENABLED, body.gibberish_enabled)
        bump_and_reload(request)  # горячий reload детектора на этом воркере
    return _relevant_settings(request)


@router.post("/relevant")
def create_relevant(body: RelevantIn, request: Request):
    relevant = db(request).relevant
    if relevant.find_by("type", body.type):
        raise HTTPException(400, "категория с таким типом уже есть")
    category = relevant.create(type=body.type, text=body.text, enabled=True)
    bump_and_reload(request)
    return relevant_out(category)


@router.patch("/relevant/{cat_id}")
def update_relevant(cat_id: int, body: RelevantPatch, request: Request):
    relevant = db(request).relevant
    current = relevant.get(cat_id)
    if not current:
        raise HTTPException(404, "category not found")
    if body.type is not None and body.type != current.type and relevant.find_by("type", body.type):
        raise HTTPException(400, "категория с таким типом уже есть")
    category = relevant.update(cat_id, body.model_dump())
    bump_and_reload(request)
    return relevant_out(category)


@router.delete("/relevant/{cat_id}")
def delete_relevant(cat_id: int, request: Request):
    if not db(request).relevant.delete(cat_id):
        raise HTTPException(404, "category not found")
    bump_and_reload(request)
    return {"deleted": cat_id}
