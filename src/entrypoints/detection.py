import json
import time

from fastapi import Request


def run_detect(request: Request, module: str, text: str, metadata: dict | None = None) -> dict:
    guard = request.app.state.guard
    started = time.perf_counter()
    result = guard.detect(module, text)
    duration_ms = (time.perf_counter() - started) * 1000
    request.app.state.runlog.log(
        module=module,
        input_text=text,
        output=json.dumps(result, ensure_ascii=False),
        duration_ms=duration_ms,
        meta=metadata,
    )
    return result


def run_batch(request: Request, module: str, texts: list[str]) -> dict:
    guard = request.app.state.guard
    return {"results": [guard.detect(module, text) for text in texts]}
