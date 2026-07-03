import test from "node:test";
import assert from "node:assert/strict";

import { APIError, AuthError, GuardrailsClient, RateLimitError } from "../src/index.js";

// Мок fetch: отдаёт заранее заданные ответы и пишет полученные запросы.
function mockFetch(responses) {
  const calls = [];
  const queue = Array.isArray(responses) ? [...responses] : [responses];
  const fn = async (url, opts) => {
    calls.push({ url, opts });
    const next = queue.length > 1 ? queue.shift() : queue[0];
    if (next instanceof Error) throw next;
    return next;
  };
  fn.calls = calls;
  return fn;
}

const json = (status, bodyObj, headers = {}) =>
  new Response(JSON.stringify(bodyObj), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

const client = (fetchImpl, opts = {}) =>
  new GuardrailsClient("http://guard.test/", "gk_test", { fetch: fetchImpl, ...opts });

test("detectPii: шлёт X-API-Key и путь /v1, возвращает JSON", async () => {
  const f = mockFetch(json(200, { PII_DETECT: true, data: [] }));
  const out = await client(f).detectPii("+79161234567");
  assert.equal(out.PII_DETECT, true);
  assert.equal(f.calls[0].url, "http://guard.test/v1/detect/pii");
  assert.equal(f.calls[0].opts.headers["X-API-Key"], "gk_test");
  assert.deepEqual(JSON.parse(f.calls[0].opts.body), { text: "+79161234567" });
});

test("metadata попадает в тело, когда передан", async () => {
  const f = mockFetch(json(200, {}));
  await client(f).detectNsfw("txt", { user_id: "42" });
  assert.deepEqual(JSON.parse(f.calls[0].opts.body), { text: "txt", metadata: { user_id: "42" } });
});

test("anonymize по умолчанию deanonymize=false", async () => {
  const f = mockFetch(json(200, { id: null, text: "почта <EMAIL_1>" }));
  await client(f).anonymize("почта a@b.ru");
  assert.deepEqual(JSON.parse(f.calls[0].opts.body), { text: "почта a@b.ru", deanonymize: false });
});

test("deanonymize шлёт id и text", async () => {
  const f = mockFetch(json(200, { text: "почта a@b.ru" }));
  await client(f).deanonymize("abc123", "почта <EMAIL_1>");
  assert.equal(f.calls[0].url, "http://guard.test/v1/deanonymize");
  assert.deepEqual(JSON.parse(f.calls[0].opts.body), { id: "abc123", text: "почта <EMAIL_1>" });
});

test("401 -> AuthError", async () => {
  const f = mockFetch(json(401, { detail: "no key" }));
  await assert.rejects(() => client(f).detectPii("x"), AuthError);
});

test("429 -> RateLimitError c retryAfter", async () => {
  const f = mockFetch(json(429, { detail: "limit" }, { "Retry-After": "7" }));
  await assert.rejects(
    () => client(f).detectPii("x"),
    (e) => e instanceof RateLimitError && e.retryAfter === 7,
  );
});

test("5xx ретраится и затем успех", async () => {
  const f = mockFetch([json(503, { detail: "down" }), json(200, { PII_DETECT: false, data: [] })]);
  const out = await client(f, { maxRetries: 2 }).detectPii("x");
  assert.equal(out.PII_DETECT, false);
  assert.equal(f.calls.length, 2);
});

test("4xx (не 401/429) -> APIError со statusCode", async () => {
  const f = mockFetch(json(400, { detail: "bad regex" }));
  await assert.rejects(
    () => client(f).detectPii("x"),
    (e) => e instanceof APIError && e.statusCode === 400,
  );
});

test("сетевой сбой после исчерпания ретраев -> APIError", async () => {
  const f = mockFetch(new TypeError("fetch failed"));
  await assert.rejects(() => client(f, { maxRetries: 1 }).detectPii("x"), APIError);
  assert.equal(f.calls.length, 2); // 1 попытка + 1 ретрай
});

test("batch: список уходит как texts", async () => {
  const f = mockFetch(json(200, { results: [] }));
  await client(f).detectRelevantBatch(["a", "b"]);
  assert.deepEqual(JSON.parse(f.calls[0].opts.body), { texts: ["a", "b"] });
});
