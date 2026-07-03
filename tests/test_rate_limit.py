"""Тесты rate limit по API-ключу.

Проверяем: персональный лимит режет на N+1 запросе (429 + Retry-After),
заголовки X-RateLimit-* отдаются, лимит 0 = без ограничения, глобальный дефолт
применяется к ключам без своего лимита, и fail-open при недоступном лимитере.
"""

from backend.config import settings


def _hit(client, key):
    return client.post("/v1/detect/nsfw", json={"text": "привет"}, headers={"X-API-Key": key})


def test_per_key_limit_blocks_after_quota(client, issue_key):
    key = issue_key(rate_limit_per_min=2)

    r1 = _hit(client, key)
    r2 = _hit(client, key)
    r3 = _hit(client, key)

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.headers["X-RateLimit-Limit"] == "2"
    assert r1.headers["X-RateLimit-Remaining"] == "1"
    assert r2.headers["X-RateLimit-Remaining"] == "0"
    assert r3.status_code == 429
    assert int(r3.headers["Retry-After"]) > 0


def test_zero_limit_means_unlimited(client, issue_key, monkeypatch):
    # дефолт низкий: если бы 0 трактовался как "не задан", ключ упёрся бы в дефолт
    monkeypatch.setattr(settings, "rate_limit_default_per_min", 3)
    key = issue_key(rate_limit_per_min=0)

    for _ in range(10):
        assert _hit(client, key).status_code == 200


def test_global_default_applies_without_per_key(client, issue_key, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_default_per_min", 1)
    key = issue_key()  # без своего лимита -> дефолт

    assert _hit(client, key).status_code == 200
    assert _hit(client, key).status_code == 429


def test_fail_open_when_limiter_unavailable(client, issue_key, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_default_per_min", 1)
    client.app.state.rate_limiter = None  # Redis «недоступен»
    key = issue_key()

    for _ in range(5):
        assert _hit(client, key).status_code == 200
