// Изоморфный клиент lite-guardrails поверх нативного fetch (Node 18+ / браузер).
//
// Берёт на себя: подстановку X-API-Key, таймаут (AbortController), ретраи на
// сетевые/5xx ошибки, разбор 401/429 в типизированные исключения.
// Публичный контракт — /v1.

import { APIError, AuthError, RateLimitError } from "./errors.js";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class GuardrailsClient {
  /**
   * @param {string} baseUrl        напр. "https://guard.company.ru"
   * @param {string} apiKey         ключ вида "gk_..."
   * @param {object} [opts]
   * @param {number} [opts.timeout=10000]   таймаут запроса, мс
   * @param {number} [opts.maxRetries=2]    ретраи на сеть/5xx
   * @param {Function} [opts.fetch]         своя реализация fetch (тесты / Node < 18)
   */
  constructor(baseUrl, apiKey, { timeout = 10000, maxRetries = 2, fetch: fetchImpl } = {}) {
    if (!baseUrl) throw new Error("baseUrl обязателен");
    if (!apiKey) throw new Error("apiKey обязателен");
    this._baseUrl = baseUrl.replace(/\/+$/, "");
    this._apiKey = apiKey;
    this._timeout = timeout;
    this._maxRetries = maxRetries;
    this._fetch = fetchImpl || globalThis.fetch;
    if (!this._fetch) {
      throw new Error("fetch недоступен — передайте { fetch } (например, node-fetch на Node < 18)");
    }
  }

  // --- детекция ---
  detectPii(text, metadata) { return this._post("/v1/detect/pii", body(text, metadata)); }
  detectNsfw(text, metadata) { return this._post("/v1/detect/nsfw", body(text, metadata)); }
  detectRelevant(text, metadata) { return this._post("/v1/detect/relevant", body(text, metadata)); }

  detectPiiBatch(texts) { return this._post("/v1/detect/pii/batch", { texts: [...texts] }); }
  detectNsfwBatch(texts) { return this._post("/v1/detect/nsfw/batch", { texts: [...texts] }); }
  detectRelevantBatch(texts) { return this._post("/v1/detect/relevant/batch", { texts: [...texts] }); }

  // --- анонимизация ---
  /**
   * deanonymize=true — сохранить mapping в Redis (вернётся id), чтобы потом
   * восстановить текст. По умолчанию false: Redis не используется, id=null.
   * При true и недоступном Redis сервис вернёт 503 (-> APIError).
   */
  anonymize(text, deanonymize = false) {
    return this._post("/v1/anonymize", { text, deanonymize });
  }

  anonymizeBatch(texts, deanonymize = false) {
    return this._post("/v1/anonymize/batch", { texts: [...texts], deanonymize });
  }

  deanonymize(mappingId, text) {
    return this._post("/v1/deanonymize", { id: mappingId, text });
  }

  // --- транспорт ---
  async _post(path, payload) {
    for (let attempt = 0; attempt <= this._maxRetries; attempt++) {
      const last = attempt === this._maxRetries;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this._timeout);
      let res;
      try {
        res = await this._fetch(`${this._baseUrl}${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-API-Key": this._apiKey },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
      } catch (e) {
        // сетевой сбой или таймаут (abort)
        if (last) throw new APIError(`transport error: ${e.message}`);
        await sleep(200 * (attempt + 1));
        continue;
      } finally {
        clearTimeout(timer);
      }

      if (res.status === 401) throw new AuthError("невалидный или отсутствующий API-ключ");
      if (res.status === 429) {
        const retryAfter = parseInt(res.headers.get("Retry-After") || "0", 10) || 0;
        throw new RateLimitError("превышен лимит запросов", retryAfter);
      }
      if (res.status >= 500 && !last) {
        await sleep(200 * (attempt + 1));
        continue;
      }
      if (res.status >= 400) {
        throw new APIError(`${res.status}: ${await detail(res)}`, res.status);
      }
      return res.json();
    }
  }
}

function body(text, metadata) {
  return metadata ? { text, metadata } : { text };
}

async function detail(res) {
  try {
    const j = await res.json();
    return j.detail ?? res.statusText;
  } catch {
    return res.statusText;
  }
}
