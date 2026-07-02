from fastapi import APIRouter, Request

from backend.entrypoints.detectors.detection import run_batch, run_detect
from backend.entrypoints.detectors.schemas import BatchIn, TextIn

router = APIRouter(tags=["relevant"])


@router.post("/detect/relevant")
async def detect_relevant(body: TextIn, request: Request):
    return run_detect(request, "relevant", body.text, body.metadata)


@router.post("/detect/relevant/batch")
async def detect_relevant_batch(body: BatchIn, request: Request):
    return run_batch(request, "relevant", body.texts)
