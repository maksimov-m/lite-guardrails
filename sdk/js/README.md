# lite-guardrails-client (JS)

Тонкий JavaScript/TypeScript-клиент для сервиса [lite-guardrails](../../README.md).
Изоморфный: работает в Node 18+ и в браузере на нативном `fetch`, **без зависимостей**.
Берёт на себя подстановку ключа, таймаут, ретраи и разбор ошибок.

## Установка

```bash
npm install ./sdk/js        # локально из репозитория
```

Или скопировать `sdk/js/src` в проект — зависимостей нет.

## Использование

```js
import { GuardrailsClient, RateLimitError } from "lite-guardrails-client";

const guard = new GuardrailsClient("https://guard.company.ru", "gk_...");

const out = await guard.detectPii("мой телефон +79161234567");
if (out.PII_DETECT) {
  // ...
}

// по умолчанию анонимизация без сохранения (Redis не используется, id=null)
await guard.anonymize("почта ivan@example.com");        // { id: null, text: "почта <EMAIL_1>" }

// deanonymize=true — сохранить mapping в Redis, чтобы потом восстановить
const masked = await guard.anonymize("почта ivan@example.com", true); // { id, text }
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

```js
new GuardrailsClient(baseUrl, apiKey, {
  timeout: 10000,   // мс, таймаут запроса (AbortController)
  maxRetries: 2,    // ретраи на сеть/5xx
  fetch: customFetch, // своя реализация (тесты; Node < 18 — например node-fetch)
});
```

## Методы

`detectPii` · `detectNsfw` · `detectRelevant` (+ `...Batch`) ·
`anonymize` / `anonymizeBatch` (флаг `deanonymize`, по умолчанию `false`) ·
`deanonymize`. Все — поверх версионированного контракта `/v1`.

## Тесты

```bash
cd sdk/js && npm test        # node --test, мок fetch, без реального сервера
```
