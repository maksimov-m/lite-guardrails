# lite-guardrails-client

Тонкий Python-клиент для сервиса [lite-guardrails](../../README.md). Берёт на себя
подстановку ключа, таймауты, ретраи и разбор ошибок — вместо ручного `httpx`/`requests`.

## Установка

```bash
pip install ./sdk/python        # локально из репозитория
```

## Использование

```python
from lite_guardrails_client import GuardrailsClient, RateLimitError

with GuardrailsClient("https://guard.company.ru", api_key="gk_...") as guard:
    out = guard.detect_pii("мой телефон +79161234567")
    if out["PII_DETECT"]:
        ...

    # по умолчанию анонимизация без сохранения (Redis не используется, id=null)
    guard.anonymize("почта ivan@example.com")            # {"id": null, "text":"почта <EMAIL_1>"}

    # deanonymize=True — сохранить mapping в Redis, чтобы потом восстановить
    masked = guard.anonymize("почта ivan@example.com", deanonymize=True)  # {"id":..., "text":...}
    original = guard.deanonymize(masked["id"], masked["text"])

    # батч
    guard.detect_nsfw_batch(["текст 1", "текст 2"])
```

Ошибки типизированы: `AuthError` (401), `RateLimitError` (429, с полем
`retry_after`), `APIError` (прочее). Сетевые сбои и 5xx ретраятся автоматически
(`max_retries`, по умолчанию 2); 429 не ретраится — решает вызывающий:

```python
try:
    guard.detect_pii(text)
except RateLimitError as e:
    time.sleep(e.retry_after)
```

## Методы

`detect_pii` · `detect_nsfw` · `detect_relevant` (+ `_batch`) ·
`anonymize` / `anonymize_batch` (флаг `deanonymize`, по умолчанию `False`) · `deanonymize`.
Все — поверх версионированного контракта `/v1`.

## Тесты

```bash
cd sdk/python && pytest        # httpx MockTransport, без реального сервера
```
