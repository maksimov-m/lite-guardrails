import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import desc, select

from src.adapters.db import (
    Dictionary,
    Rule,
    RunLog,
    SessionLocal,
    bump_version,
    get_version,
)

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin")
MAX_REGEX_LEN = 1000

router = APIRouter(prefix="/admin", tags=["admin"])


# --- авторизация -----------------------------------------------------------
def require_admin(x_admin_token: str = Header(default="")):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "invalid admin token")


# --- валидация regex: только синтаксис и длина -----------------------------
# Админ доверенный, поэтому ReDoS-песочницу не делаем; проверяем, что паттерн
# вообще компилируется и не абсурдно длинный.
def validate_regex(pattern: str):
    if len(pattern) > MAX_REGEX_LEN:
        raise HTTPException(400, f"regex слишком длинный (> {MAX_REGEX_LEN})")
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise HTTPException(400, f"невалидный regex: {e}")


# --- модели ----------------------------------------------------------------
class RuleIn(BaseModel):
    module: str          # pii | nsfw | relevant
    label: str | None = None
    value: str
    enabled: bool = True


class RulePatch(BaseModel):
    label: str | None = None
    value: str | None = None
    enabled: bool | None = None


def _serialize(r: Rule) -> dict:
    return {"id": r.id, "module": r.module, "label": r.label,
            "value": r.value, "enabled": r.enabled}


def _autoapply(request: Request):
    """Авто-применение: bump версии + немедленный reload этого воркера."""
    bump_version()
    request.app.state.guard.reload()


# --- CRUD правил -----------------------------------------------------------
@router.get("/rules", dependencies=[Depends(require_admin)])
def list_rules(module: str | None = None, label: str | None = None,
               limit: int = 5000, offset: int = 0):
    with SessionLocal() as s:
        q = select(Rule).order_by(Rule.module, Rule.label, Rule.id)
        if module:
            q = q.where(Rule.module == module)
        if label is not None:
            q = q.where(Rule.label == label)
        rows = s.scalars(q.limit(limit).offset(offset)).all()
        return {"rules": [_serialize(r) for r in rows]}


@router.post("/rules", dependencies=[Depends(require_admin)])
def create_rule(body: RuleIn, request: Request):
    if body.module not in ("pii", "nsfw", "relevant"):
        raise HTTPException(400, "module: pii|nsfw|relevant")
    if body.module == "pii":
        validate_regex(body.value)        # PII value — это regex
    with SessionLocal() as s:
        rule = Rule(module=body.module, label=body.label,
                    value=body.value, enabled=body.enabled)
        s.add(rule)
        s.commit()
        out = _serialize(rule)
    _autoapply(request)
    return out


@router.patch("/rules/{rule_id}", dependencies=[Depends(require_admin)])
def update_rule(rule_id: int, body: RulePatch, request: Request):
    with SessionLocal() as s:
        rule = s.get(Rule, rule_id)
        if not rule:
            raise HTTPException(404, "rule not found")
        if body.value is not None and rule.module == "pii":
            validate_regex(body.value)
        for field in ("label", "value", "enabled"):
            v = getattr(body, field)
            if v is not None:
                setattr(rule, field, v)
        s.commit()
        out = _serialize(rule)
    _autoapply(request)
    return out


@router.delete("/rules/{rule_id}", dependencies=[Depends(require_admin)])
def delete_rule(rule_id: int, request: Request):
    with SessionLocal() as s:
        rule = s.get(Rule, rule_id)
        if not rule:
            raise HTTPException(404, "rule not found")
        s.delete(rule)
        s.commit()
    _autoapply(request)
    return {"deleted": rule_id}


# --- словари NSFW ----------------------------------------------------------
class DictIn(BaseModel):
    name: str


class DictPatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None


@router.get("/dicts", dependencies=[Depends(require_admin)])
def list_dicts():
    with SessionLocal() as s:
        dicts = s.scalars(select(Dictionary).order_by(Dictionary.id)).all()
        # счётчик слов по словарям (для пользовательских)
        counts = {}
        for r in s.scalars(select(Rule).where(Rule.module == "nsfw")).all():
            counts[r.label] = counts.get(r.label, 0) + 1
        return {"dicts": [{
            "id": d.id, "name": d.name, "enabled": d.enabled,
            "builtin": d.builtin, "word_count": counts.get(d.name, 0),
        } for d in dicts]}


@router.post("/dicts", dependencies=[Depends(require_admin)])
def create_dict(body: DictIn, request: Request):
    with SessionLocal() as s:
        if s.scalar(select(Dictionary).where(Dictionary.name == body.name)):
            raise HTTPException(400, "словарь с таким именем уже есть")
        d = Dictionary(name=body.name, enabled=True, builtin=False)
        s.add(d)
        s.commit()
        out = {"id": d.id, "name": d.name, "enabled": d.enabled, "builtin": False}
    _autoapply(request)
    return out


@router.patch("/dicts/{dict_id}", dependencies=[Depends(require_admin)])
def update_dict(dict_id: int, body: DictPatch, request: Request):
    with SessionLocal() as s:
        d = s.get(Dictionary, dict_id)
        if not d:
            raise HTTPException(404, "dict not found")
        if body.enabled is not None:
            d.enabled = body.enabled
        if body.name is not None and not d.builtin:
            # переименование тянет переименование слов (label)
            for r in s.scalars(select(Rule).where(
                    Rule.module == "nsfw", Rule.label == d.name)).all():
                r.label = body.name
            d.name = body.name
        s.commit()
        out = {"id": d.id, "name": d.name, "enabled": d.enabled, "builtin": d.builtin}
    _autoapply(request)
    return out


@router.get("/dicts/{dict_id}/export", dependencies=[Depends(require_admin)])
def export_dict(dict_id: int, request: Request):
    """Выгрузка слов словаря в .txt (по слову на строку, отсортировано)."""
    with SessionLocal() as s:
        d = s.get(Dictionary, dict_id)
        if not d:
            raise HTTPException(404, "dict not found")
        if d.builtin:
            words = request.app.state.guard._nsfw_builtin
        else:
            words = [r.value for r in s.scalars(select(Rule).where(
                Rule.module == "nsfw", Rule.label == d.name)).all()]
        name = d.name
    body = "\n".join(sorted(words))
    # HTTP-заголовок только latin-1: кириллицу выкидываем, фронт всё равно
    # подставляет своё человекочитаемое имя файла.
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "dict"
    return PlainTextResponse(body, headers={
        "Content-Disposition": f'attachment; filename="{safe}.txt"',
    })


@router.delete("/dicts/{dict_id}", dependencies=[Depends(require_admin)])
def delete_dict(dict_id: int, request: Request):
    with SessionLocal() as s:
        d = s.get(Dictionary, dict_id)
        if not d:
            raise HTTPException(404, "dict not found")
        if d.builtin:
            raise HTTPException(400, "встроенный словарь нельзя удалить")
        for r in s.scalars(select(Rule).where(
                Rule.module == "nsfw", Rule.label == d.name)).all():
            s.delete(r)
        s.delete(d)
        s.commit()
    _autoapply(request)
    return {"deleted": dict_id}


@router.get("/version", dependencies=[Depends(require_admin)])
def version(request: Request):
    return {"db_version": get_version(), "active_version": request.app.state.guard.version}


# --- логи прогонов ---------------------------------------------------------
@router.get("/logs", dependencies=[Depends(require_admin)])
def logs(module: str | None = None, limit: int = 100,
         meta_key: str | None = None, meta_value: str | None = None):
    with SessionLocal() as s:
        q = select(RunLog).order_by(desc(RunLog.created_at))
        if module:
            q = q.where(RunLog.module == module)
        if meta_key:
            # value задан -> точное совпадение по ключу; иначе -> просто наличие ключа
            if meta_value not in (None, ""):
                q = q.where(RunLog.meta[meta_key].astext == meta_value)
            else:
                q = q.where(RunLog.meta.has_key(meta_key))  # noqa: W601 (JSONB ?)
        rows = s.scalars(q.limit(min(limit, 1000))).all()
        return {"logs": [{
            "id": r.id, "ts": r.created_at.isoformat(), "module": r.module,
            "input": r.input_text, "output": r.output,
            "duration_ms": round(r.duration_ms, 3), "meta": r.meta,
        } for r in rows]}


@router.get("/logs/meta-keys", dependencies=[Depends(require_admin)])
def logs_meta_keys():
    """Список всех встречающихся в логах ключей metadata (для фильтра в UI)."""
    from sqlalchemy import text
    with SessionLocal() as s:
        rows = s.execute(text(
            "SELECT DISTINCT jsonb_object_keys(meta) AS k FROM run_logs "
            "WHERE jsonb_typeof(meta) = 'object' ORDER BY k"
        )).all()
        return {"keys": [r.k for r in rows]}
