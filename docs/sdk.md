# Python SDK

Тонкий клиент поверх `httpx`: подставляет ключ, делает ретраи на сеть/5xx,
разбирает ошибки в типизированные исключения. Пакет — в репозитории (`sdk/python`).

## Установка

```bash
pip install ./sdk/python
```

## Использование

```python
from lite_guardrails_client import GuardrailsClient, RateLimitError

with GuardrailsClient("http://localhost:8000", api_key="gk_...") as guard:
    out = guard.detect_pii("мой телефон +79161234567")
    if out["PII_DETECT"]:
        ...

    # по умолчанию — без сохранения (Redis не используется, id=null)
    guard.anonymize("почта ivan@example.com")

    # deanonymize=True — сохранить mapping в Redis для восстановления
    masked = guard.anonymize("почта ivan@example.com", deanonymize=True)
    original = guard.deanonymize(masked["id"], masked["text"])

    # батч
    guard.detect_nsfw_batch(["текст 1", "текст 2"])
```

## Обработка ошибок

Исключения типизированы: `AuthError` (401), `RateLimitError` (429, с полем
`retry_after`), `APIError` (прочее, включая `503` при `deanonymize=True` и
недоступном Redis). Сетевые сбои и 5xx ретраятся автоматически (`max_retries`,
по умолчанию 2); `429` не ретраится — решает вызывающий:

```python
import time

try:
    guard.detect_pii(text)
except RateLimitError as e:
    time.sleep(e.retry_after)
    guard.detect_pii(text)
```

## Методы

`detect_pii` · `detect_nsfw` · `detect_relevant` (+ `_batch`) ·
`anonymize` / `anonymize_batch` (флаг `deanonymize`, по умолчанию `False`) ·
`deanonymize`. Все — поверх версионированного контракта `/v1`.
