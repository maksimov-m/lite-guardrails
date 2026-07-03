"""NSFW: словари (имя + текст со словами)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from backend.entrypoints.admin.schemas import NsfwDictIn, NsfwDictPatch
from backend.entrypoints.admin.utils import bump_and_reload, db, nsfw_out, safe_filename

router = APIRouter()


@router.get("/nsfw")
def list_nsfw(request: Request):
    return {"dicts": [nsfw_out(d) for d in db(request).nsfw.list()]}


@router.get("/nsfw/{dict_id}")
def get_nsfw(dict_id: int, request: Request):
    """Полный словарь вместе с текстом слов — для редактирования в UI
    (в list текст намеренно не отдаём: встроенный словарь большой)."""
    dictionary = db(request).nsfw.get(dict_id)
    if not dictionary:
        raise HTTPException(404, "dict not found")
    return {**nsfw_out(dictionary), "text": dictionary.text}


@router.post("/nsfw")
def create_nsfw(body: NsfwDictIn, request: Request):
    nsfw = db(request).nsfw
    if nsfw.find_by("name", body.name):
        raise HTTPException(400, "словарь с таким именем уже есть")
    dictionary = nsfw.create(name=body.name, text=body.text, enabled=True)
    bump_and_reload(request)
    return nsfw_out(dictionary)


@router.patch("/nsfw/{dict_id}")
def update_nsfw(dict_id: int, body: NsfwDictPatch, request: Request):
    nsfw = db(request).nsfw
    current = nsfw.get(dict_id)
    if not current:
        raise HTTPException(404, "dict not found")
    if body.name is not None and body.name != current.name and nsfw.find_by("name", body.name):
        raise HTTPException(400, "словарь с таким именем уже есть")
    dictionary = nsfw.update(dict_id, body.model_dump())
    bump_and_reload(request)
    return nsfw_out(dictionary)


@router.get("/nsfw/{dict_id}/export")
def export_nsfw(dict_id: int, request: Request):
    dictionary = db(request).nsfw.get(dict_id)
    if not dictionary:
        raise HTTPException(404, "dict not found")
    return PlainTextResponse(
        dictionary.text,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename(dictionary.name)}.txt"'
        },
    )


@router.delete("/nsfw/{dict_id}")
def delete_nsfw(dict_id: int, request: Request):
    if not db(request).nsfw.delete(dict_id):
        raise HTTPException(404, "dict not found")
    bump_and_reload(request)
    return {"deleted": dict_id}
