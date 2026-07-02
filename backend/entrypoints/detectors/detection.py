import json
import time
import uuid

from fastapi import Request

from backend.entrypoints.detectors.log_utils import build_log_payload, meta_with_key


def run_detect(request: Request, module: str, text: str, metadata: dict | None = None) -> dict:
    guard = request.app.state.guard
    started = time.perf_counter()
    result = guard.detect(module, text)
    duration_ms = (time.perf_counter() - started) * 1000
    # В логи кладём анонимизированную копию, если вызывался модуль pii.
    log_text, log_output = build_log_payload(module, text, result)
    request.app.state.runlog.log(
        module=module,
        input_text=log_text,
        output=json.dumps(log_output, ensure_ascii=False),
        duration_ms=duration_ms,
        meta=meta_with_key(request, metadata),
    )
    return result


def run_batch(request: Request, module: str, texts: list[str]) -> dict:
    guard = request.app.state.guard
    return {"results": [guard.detect(module, text) for text in texts]}


def anonymize_text(request: Request, text: str) -> dict:
    anonymized, mapping = request.app.state.guard.pii.anonymize(text)
    mapping_id = None
    if mapping:
        mapping_id = uuid.uuid4().hex
        request.app.state.store.save(mapping_id, mapping)
    return {"id": mapping_id, "text": anonymized}


def deanonymize_text(request: Request, mapping_id: str, text: str) -> str | None:
    mapping = request.app.state.store.get(mapping_id)
    if mapping is None:
        return None
    return request.app.state.guard.pii.deanonymize(text, mapping)


def anonymize_batch(request: Request, texts: list[str]) -> list[dict]:
    return [anonymize_text(request, text) for text in texts]


def deanonymize_batch(request: Request, items: list) -> list[dict]:
    results = []
    for item in items:
        restored = deanonymize_text(request, item.id, item.text)
        results.append({
            "text": item.text if restored is None else restored,
            "restored": restored is not None,
        })
    return results
