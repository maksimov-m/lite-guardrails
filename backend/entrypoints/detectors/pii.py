from fastapi import APIRouter, HTTPException, Request

from backend.entrypoints.detectors.detection import (
    anonymize_batch,
    anonymize_text,
    deanonymize_batch,
    deanonymize_text,
    run_batch,
    run_detect,
)
from backend.entrypoints.detectors.schemas import BatchIn, DeanonymizeBatchIn, DeanonymizeIn, TextIn

router = APIRouter(tags=["pii"])


@router.post("/detect/pii")
async def detect_pii(body: TextIn, request: Request):
    return run_detect(request, "pii", body.text, body.metadata)


@router.post("/detect/pii/batch")
async def detect_pii_batch(body: BatchIn, request: Request):
    return run_batch(request, "pii", body.texts)


@router.post("/anonymize")
async def anonymize(body: TextIn, request: Request):
    return anonymize_text(request, body.text)


@router.post("/anonymize/batch")
async def anonymize_texts(body: BatchIn, request: Request):
    return {"results": anonymize_batch(request, body.texts)}


@router.post("/deanonymize")
async def deanonymize(body: DeanonymizeIn, request: Request):
    restored = deanonymize_text(request, body.id, body.text)
    if restored is None:
        raise HTTPException(404, "mapping not found (неизвестный id или истёк TTL)")
    return {"text": restored}


@router.post("/deanonymize/batch")
async def deanonymize_texts(body: DeanonymizeBatchIn, request: Request):
    return {"results": deanonymize_batch(request, body.items)}
