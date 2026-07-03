import json
import time
import uuid

from fastapi import HTTPException, Request

from backend.entrypoints.detectors.log_utils import build_log_payload, meta_with_key


def _is_detection(module: str, result: dict) -> bool:
    """Сработал ли гуард. Для relevant это RELEVANT=false (пойман чит-чат/атака),
    для остальных — <MODULE>_DETECT=true. Совпадает с SQL-логикой в run_log_stats;
    считаем здесь (результат уже на руках), чтобы не парсить output в БД."""
    if module == "relevant":
        return result.get("RELEVANT") is False
    return result.get(f"{module.upper()}_DETECT") is True


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
        detected=_is_detection(module, result),
    )
    return result


def run_batch(request: Request, module: str, texts: list[str]) -> dict:
    guard = request.app.state.guard
    return {"results": [guard.detect(module, text) for text in texts]}


def _require_store(request: Request) -> None:
    """deanonymize=true невозможен без Redis (там хранится mapping) — падаем явно,
    а не молча теряем обратимость. Проверяем доступность один раз на запрос."""
    store = request.app.state.store
    try:
        available = store.ping()
    except Exception:
        available = False
    if not available:
        raise HTTPException(503, "deanonymize=true требует доступного Redis, но он недоступен")


def _anonymize_one(request: Request, text: str, store_mapping: bool) -> dict:
    anonymized, mapping = request.app.state.guard.pii.anonymize(text)
    mapping_id = None
    # mapping в Redis сохраняем только под deanonymize=true (иначе Redis не трогаем).
    if store_mapping and mapping:
        mapping_id = uuid.uuid4().hex
        request.app.state.store.save(mapping_id, mapping)
    return {"id": mapping_id, "text": anonymized}


def anonymize_text(request: Request, text: str, deanonymize: bool = False) -> dict:
    if deanonymize:
        _require_store(request)
    return _anonymize_one(request, text, deanonymize)


def deanonymize_text(request: Request, mapping_id: str, text: str) -> str | None:
    mapping = request.app.state.store.get(mapping_id)
    if mapping is None:
        return None
    return request.app.state.guard.pii.deanonymize(text, mapping)


def anonymize_batch(request: Request, texts: list[str], deanonymize: bool = False) -> list[dict]:
    if deanonymize:
        _require_store(request)  # проверяем Redis один раз на весь батч
    return [_anonymize_one(request, text, deanonymize) for text in texts]


def deanonymize_batch(request: Request, items: list) -> list[dict]:
    results = []
    for item in items:
        restored = deanonymize_text(request, item.id, item.text)
        results.append(
            {
                "text": item.text if restored is None else restored,
                "restored": restored is not None,
            }
        )
    return results
