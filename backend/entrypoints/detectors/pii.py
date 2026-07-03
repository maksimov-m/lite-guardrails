from fastapi import APIRouter, HTTPException, Request

from backend.entrypoints.detectors.detection import (
    anonymize_batch,
    anonymize_text,
    deanonymize_batch,
    deanonymize_text,
    run_batch,
    run_detect,
)
from backend.entrypoints.detectors.schemas import (
    AnonymizeBatchIn,
    AnonymizeIn,
    BatchIn,
    DeanonymizeBatchIn,
    DeanonymizeIn,
    TextIn,
)

router = APIRouter(tags=["pii"])


# Хендлеры — обычные def (не async): детекция CPU-bound + redis-py блокирующие.
# FastAPI уводит sync-хендлеры в threadpool, поэтому они не блокируют event loop
# (иначе один большой батч заморозил бы весь воркер, включая /live). См. health.py.
@router.post("/detect/pii")
def detect_pii(body: TextIn, request: Request):
    return run_detect(request, "pii", body.text, body.metadata)


@router.post("/detect/pii/batch")
def detect_pii_batch(body: BatchIn, request: Request):
    return run_batch(request, "pii", body.texts)


@router.post("/anonymize")
def anonymize(body: AnonymizeIn, request: Request):
    return anonymize_text(request, body.text, body.deanonymize)


@router.post("/anonymize/batch")
def anonymize_texts(body: AnonymizeBatchIn, request: Request):
    return {"results": anonymize_batch(request, body.texts, body.deanonymize)}


@router.post("/deanonymize")
def deanonymize(body: DeanonymizeIn, request: Request):
    restored = deanonymize_text(request, body.id, body.text)
    if restored is None:
        raise HTTPException(404, "mapping not found (неизвестный id или истёк TTL)")
    return {"text": restored}


@router.post("/deanonymize/batch")
def deanonymize_texts(body: DeanonymizeBatchIn, request: Request):
    return {"results": deanonymize_batch(request, body.items)}
