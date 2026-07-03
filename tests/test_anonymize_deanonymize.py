"""Флаг deanonymize у /v1/anonymize.

По умолчанию false — Redis не трогаем, id=null. При true сохраняем mapping в
Redis (возвращается id, текст восстановим). Если Redis недоступен, а запросили
deanonymize=true — явная ошибка 503, а не молчаливая потеря обратимости.
"""

import pytest

TEXT = "почта ivan@example.com"


@pytest.fixture
def seeded(client, admin_headers, auth_headers):
    """Клиент с засеянным email-правилом и готовыми auth-заголовками.
    В in-memory сборке PII-правил нет (в проде их сидит DEFAULT_PATTERNS)."""
    r = client.post(
        "/admin/pii",
        json={"type": "email", "regex": r"[\w.+-]+@[\w-]+\.[\w.-]+"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    return client, auth_headers


def test_default_no_deanonymize_no_id(seeded):
    client, headers = seeded

    a = client.post("/v1/anonymize", json={"text": TEXT}, headers=headers).json()

    assert a["id"] is None  # по умолчанию mapping не хранится
    assert "ivan@example.com" not in a["text"]  # но анонимизация произошла


def test_deanonymize_true_stores_and_restores(seeded):
    client, headers = seeded

    a = client.post(
        "/v1/anonymize", json={"text": TEXT, "deanonymize": True}, headers=headers
    ).json()
    assert a["id"] is not None

    d = client.post(
        "/v1/deanonymize", json={"id": a["id"], "text": a["text"]}, headers=headers
    ).json()
    assert "ivan@example.com" in d["text"]


def test_deanonymize_true_without_redis_raises_503(seeded):
    client, headers = seeded
    client.app.state.store.ping = lambda: False  # Redis "недоступен"

    r = client.post("/v1/anonymize", json={"text": TEXT, "deanonymize": True}, headers=headers)
    assert r.status_code == 503

    # без флага (дефолт) Redis не нужен — работает и при "недоступном" Redis
    ok = client.post("/v1/anonymize", json={"text": TEXT}, headers=headers)
    assert ok.status_code == 200 and ok.json()["id"] is None


def test_batch_deanonymize_true_without_redis_raises_503(seeded):
    client, headers = seeded
    client.app.state.store.ping = lambda: False

    r = client.post(
        "/v1/anonymize/batch", json={"texts": [TEXT], "deanonymize": True}, headers=headers
    )
    assert r.status_code == 503
