from fastapi import APIRouter, Request

from src.entrypoints.detection import run_batch, run_detect
from src.entrypoints.schemas import BatchIn, TextIn

router = APIRouter(tags=["nsfw"])


@router.post("/detect/nsfw")
async def detect_nsfw(body: TextIn, request: Request):
    return run_detect(request, "nsfw", body.text, body.metadata)


@router.post("/detect/nsfw/batch")
async def detect_nsfw_batch(body: BatchIn, request: Request):
    return run_batch(request, "nsfw", body.texts)
