import uuid

from fastapi import APIRouter, HTTPException, Request

from src.entrypoints.detection import run_batch, run_detect
from src.entrypoints.schemas import BatchIn, DeanonymizeIn, TextIn

router = APIRouter(tags=["pii"])


@router.post("/detect/pii")
async def detect_pii(body: TextIn, request: Request):
    return run_detect(request, "pii", body.text, body.metadata)


@router.post("/detect/pii/batch")
async def detect_pii_batch(body: BatchIn, request: Request):
    return run_batch(request, "pii", body.texts)


@router.post("/anonymize")
async def anonymize(body: TextIn, request: Request):
    text, mapping = request.app.state.guard.pii.anonymize(body.text)
    mapping_id = uuid.uuid4().hex
    if mapping:
        request.app.state.store.save(mapping_id, mapping)
    return {"id": mapping_id, "text": text}


@router.post("/deanonymize")
async def deanonymize(body: DeanonymizeIn, request: Request):
    mapping = request.app.state.store.get(body.id)
    if mapping is None:
        raise HTTPException(404, "mapping not found (неизвестный id или истёк TTL)")
    return {"text": request.app.state.guard.pii.deanonymize(body.text, mapping)}
