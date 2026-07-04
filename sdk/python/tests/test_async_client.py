"""Тесты async-клиента на httpx.MockTransport — без реального сервера.

Зеркалят test_client.py: путь/тело/заголовок ключа, разбор ответа и разбор
401/429 в типизированные исключения. Чтобы не тянуть pytest-asyncio, корутины
гоняем через asyncio.run (MockTransport умеет и в async-режим)."""

import asyncio
import json

import httpx
import pytest
from lite_guardrails_client import AsyncGuardrailsClient, AuthError, RateLimitError


def _client(handler):
    return AsyncGuardrailsClient("http://guard", "gk_test", transport=httpx.MockTransport(handler))


def test_detect_pii_sends_key_path_body_and_parses():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("X-API-Key")
        seen["json"] = request.content
        return httpx.Response(200, json={"PII_DETECT": True, "data": []})

    async def go():
        async with _client(handler) as c:
            return await c.detect_pii("телефон +79161234567", metadata={"user": "u1"})

    out = asyncio.run(go())
    assert seen["path"] == "/v1/detect/pii"
    assert seen["key"] == "gk_test"
    assert b"+79161234567" in seen["json"] and b"metadata" in seen["json"]
    assert out["PII_DETECT"] is True


def test_batch_path_and_payload():
    def handler(request):
        assert request.url.path == "/v1/detect/nsfw/batch"
        assert b"texts" in request.content
        return httpx.Response(200, json=[{"NSFW_DETECT": False}])

    async def go():
        async with _client(handler) as c:
            return await c.detect_nsfw_batch(["a", "b"])

    assert asyncio.run(go()) == [{"NSFW_DETECT": False}]


def test_401_raises_auth_error():
    async def go():
        async with _client(lambda r: httpx.Response(401, json={"detail": "no key"})) as c:
            await c.detect_pii("x")

    with pytest.raises(AuthError):
        asyncio.run(go())


def test_429_raises_rate_limit_with_retry_after():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "42"}, json={"detail": "slow down"})

    async def go():
        async with _client(handler) as c:
            await c.detect_pii("x")

    with pytest.raises(RateLimitError) as e:
        asyncio.run(go())
    assert e.value.retry_after == 42


def test_anonymize_deanonymize_flag_in_body():
    seen = {}

    def handler(request):
        seen["body"] = request.content
        return httpx.Response(200, json={"id": "m1", "text": "почта <EMAIL_1>"})

    async def go():
        async with _client(handler) as c:
            await c.anonymize("почта a@b.com")  # дефолт
            default_body = json.loads(seen["body"])
            await c.anonymize("почта a@b.com", deanonymize=True)  # явно
            return default_body, json.loads(seen["body"])

    default_body, explicit_body = asyncio.run(go())
    assert default_body["deanonymize"] is False
    assert explicit_body["deanonymize"] is True


def test_anonymize_roundtrip_shape():
    def handler(request):
        if request.url.path == "/v1/anonymize":
            return httpx.Response(200, json={"id": "m1", "text": "почта <EMAIL_1>"})
        return httpx.Response(200, json={"text": "почта a@b.com"})

    async def go():
        async with _client(handler) as c:
            a = await c.anonymize("почта a@b.com")
            d = await c.deanonymize("m1", "почта <EMAIL_1>")
            return a, d

    a, d = asyncio.run(go())
    assert a["id"] == "m1"
    assert d["text"] == "почта a@b.com"


def test_5xx_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"detail": "warming up"})
        return httpx.Response(200, json={"NSFW_DETECT": False})

    async def go():
        async with _client(handler) as c:
            return await c.detect_nsfw("x")

    out = asyncio.run(go())
    assert out == {"NSFW_DETECT": False}
    assert calls["n"] == 2  # первый 503 → ретрай → 200
