# JavaScript SDK

Изоморфный клиент на нативном `fetch` (Node 18+ и браузер), **без зависимостей**:
подставляет ключ, делает ретраи на сеть/5xx, разбирает ошибки в типизированные
исключения. Пакет — в репозитории (`sdk/js`).

## Установка

```bash
npm install ./sdk/js
```

Зависимостей нет — можно и просто скопировать `sdk/js/src`.

## Использование

```js
import { GuardrailsClient, RateLimitError } from "lite-guardrails-client";

const guard = new GuardrailsClient("http://localhost:8000", "gk_...");

const out = await guard.detectPii("мой телефон +79161234567");
if (out.PII_DETECT) {
  // ...
}

// по умолчанию — без сохранения (Redis не используется, id=null)
await guard.anonymize("почта ivan@example.com");

// deanonymize=true — сохранить mapping в Redis для восстановления
const masked = await guard.anonymize("почта ivan@example.com", true);
const original = await guard.deanonymize(masked.id, masked.text);

// батч
await guard.detectNsfwBatch(["текст 1", "текст 2"]);
```

## Обработка ошибок

Исключения типизированы: `AuthError` (401), `RateLimitError` (429, с полем
`retryAfter`), `APIError` (прочее, включая `503` при `deanonymize=true` и
недоступном Redis). Сетевые сбои и 5xx ретраятся автоматически (`maxRetries`,
по умолчанию 2); `429` не ретраится — решает вызывающий:

```js
try {
  await guard.detectPii(text);
} catch (e) {
  if (e instanceof RateLimitError) {
    await new Promise((r) => setTimeout(r, e.retryAfter * 1000));
    await guard.detectPii(text);
  }
}
```

## Опции конструктора

`timeout` (мс, по умолчанию 10000) · `maxRetries` (по умолчанию 2) ·
`fetch` (своя реализация — для тестов или Node < 18).

## Методы

`detectPii` · `detectNsfw` · `detectRelevant` (+ `...Batch`) ·
`anonymize` / `anonymizeBatch` (флаг `deanonymize`, по умолчанию `false`) ·
`deanonymize`. Все — поверх версионированного контракта `/v1`.
