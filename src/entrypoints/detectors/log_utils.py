"""Подготовка данных детекции к записи в run_logs (без сырых PII)."""

from fastapi import Request

from src.config import settings


def anonymize_from_spans(text: str, data: list[dict]) -> str:
    """Собрать анонимизированный текст из УЖЕ посчитанного результата PII-детекции
    (без повторного прохода детектором).

    Офсеты берём из detect(): он считает их на нормализованном тексте
    (Normalizer.normalize == str.lower, длина сохраняется), поэтому start/end
    корректно применимы к исходному тексту.
    """
    tag_by_value: dict[tuple[str, str], str] = {}
    counters: dict[str, int] = {}
    for d in sorted(data, key=lambda d: d["start"]):
        key = (d["class"], d["value"])
        if key not in tag_by_value:
            counters[d["class"]] = counters.get(d["class"], 0) + 1
            tag_by_value[key] = f"<{d['class'].upper()}_{counters[d['class']]}>"

    out = text
    for d in sorted(data, key=lambda d: d["start"], reverse=True):
        out = out[: d["start"]] + tag_by_value[(d["class"], d["value"])] + out[d["end"] :]
    return out


def build_log_payload(module: str, text: str, result: dict) -> tuple[str, dict]:
    """Что писать в логи. Анонимизируем только когда вызывался модуль pii —
    там результат детекции уже содержит спаны PII, из них и собираем текст,
    а сырые значения в output маскируем. Для остальных модулей — как есть.
    """
    if module != "pii" or settings.log_raw_input or not result.get("data"):
        return text, result
    log_text = anonymize_from_spans(text, result["data"])
    log_output = {**result, "data": [{**d, "value": None} for d in result["data"]]}
    return log_text, log_output


def meta_with_key(request: Request, metadata: dict | None) -> dict | None:
    """Дописать в метаданные, какой API-ключ обращался (для аудита в логах)."""
    info = getattr(request.state, "api_key", None)
    if info is None:
        return metadata
    return {**(metadata or {}), "api_key": info["name"], "api_key_id": info["id"]}
