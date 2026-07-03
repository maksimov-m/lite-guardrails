from fastapi import APIRouter, Request

from backend.entrypoints.detectors.detection import run_batch, run_detect
from backend.entrypoints.detectors.schemas import BatchIn, TextIn

router = APIRouter(tags=["relevant"])


# Обычный def (не async): CPU-bound детекция уходит в threadpool и не блокирует
# event loop. Подробнее — комментарий в pii.py / health.py.
@router.post("/detect/relevant")
def detect_relevant(body: TextIn, request: Request):
    return run_detect(request, "relevant", body.text, body.metadata)


@router.post("/detect/relevant/batch")
def detect_relevant_batch(body: BatchIn, request: Request):
    return run_batch(request, "relevant", body.texts)
