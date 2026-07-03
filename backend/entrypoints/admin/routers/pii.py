"""PII: regex-сигнатуры по типам."""

from fastapi import APIRouter, HTTPException, Request

from backend.entrypoints.admin.schemas import PiiRuleIn, PiiRulePatch
from backend.entrypoints.admin.utils import bump_and_reload, db, pii_out, validate_regex

router = APIRouter()


@router.get("/pii")
def list_pii(request: Request, limit: int = 50, offset: int = 0):
    rows = db(request).pii.list_page(limit + 1, offset)
    has_more = len(rows) > limit
    return {
        "rules": [pii_out(r) for r in rows[:limit]],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@router.post("/pii")
def create_pii(body: PiiRuleIn, request: Request):
    validate_regex(body.regex)
    rule = db(request).pii.create(type=body.type, regex=body.regex, enabled=body.enabled)
    bump_and_reload(request)
    return pii_out(rule)


@router.patch("/pii/{rule_id}")
def update_pii(rule_id: int, body: PiiRulePatch, request: Request):
    if body.regex is not None:
        validate_regex(body.regex)
    rule = db(request).pii.update(rule_id, body.model_dump())
    if not rule:
        raise HTTPException(404, "pii rule not found")
    bump_and_reload(request)
    return pii_out(rule)


@router.delete("/pii/{rule_id}")
def delete_pii(rule_id: int, request: Request):
    if not db(request).pii.delete(rule_id):
        raise HTTPException(404, "pii rule not found")
    bump_and_reload(request)
    return {"deleted": rule_id}
