"""Тесты клиента на httpx.MockTransport — без реального сервера.

Проверяем: правильный путь/тело/заголовок ключа, разбор ответа, и что 401/429
превращаются в типизированные исключения (429 — с retry_after)."""

import json

import httpx
import pytest
from lite_guardrails_client import AuthError, GuardrailsClient, RateLimitError


def _client(handler):
    return GuardrailsClient("http://guard", "gk_test",
                            transport=httpx.MockTransport(handler))


def test_detect_pii_sends_key_path_body_and_parses():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("X-API-Key")
        seen["json"] = request.content
        return httpx.Response(200, json={"PII_DETECT": True, "data": []})

    with _client(handler) as c:
        out = c.detect_pii("телефон +79161234567", metadata={"user": "u1"})

    assert seen["path"] == "/v1/detect/pii"
    assert seen["key"] == "gk_test"
    assert b"+79161234567" in seen["json"] and b"metadata" in seen["json"]
    assert out["PII_DETECT"] is True


def test_batch_path_and_payload():
    def handler(request):
        assert request.url.path == "/v1/detect/nsfw/batch"
        assert b"texts" in request.content
        return httpx.Response(200, json=[{"NSFW_DETECT": False}])

    with _client(handler) as c:
        assert c.detect_nsfw_batch(["a", "b"]) == [{"NSFW_DETECT": False}]


def test_401_raises_auth_error():
    with _client(lambda r: httpx.Response(401, json={"detail": "no key"})) as c:
        with pytest.raises(AuthError):
            c.detect_pii("x")


def test_429_raises_rate_limit_with_retry_after():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "42"}, json={"detail": "slow down"})

    with _client(handler) as c:
        with pytest.raises(RateLimitError) as e:
            c.detect_pii("x")
    assert e.value.retry_after == 42


def test_anonymize_deanonymize_flag_in_body():
    seen = {}

    def handler(request):
        seen["body"] = request.content
        return httpx.Response(200, json={"id": "m1", "text": "почта <EMAIL_1>"})

    with _client(handler) as c:
        c.anonymize("почта a@b.com")                     # дефолт
        default_body = json.loads(seen["body"])
        c.anonymize("почта a@b.com", deanonymize=True)   # явно
        explicit_body = json.loads(seen["body"])

    assert default_body["deanonymize"] is False
    assert explicit_body["deanonymize"] is True


def test_anonymize_roundtrip_shape():
    def handler(request):
        if request.url.path == "/v1/anonymize":
            return httpx.Response(200, json={"id": "m1", "text": "почта <EMAIL_1>"})
        return httpx.Response(200, json={"text": "почта a@b.com"})

    with _client(handler) as c:
        assert c.anonymize("почта a@b.com")["id"] == "m1"
        assert c.deanonymize("m1", "почта <EMAIL_1>")["text"] == "почта a@b.com"
