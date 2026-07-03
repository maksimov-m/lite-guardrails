"""Флаг deanonymize у /v1/anonymize.

По умолчанию false — Redis не трогаем, id=null. При true сохраняем mapping в
Redis (возвращается id, текст восстановим). Если Redis недоступен, а запросили
deanonymize=true — явная ошибка 503, а не молчаливая потеря обратимости.
"""

from inmemory import make_client

ADMIN = {"X-Admin-Token": "admin"}
TEXT = "почта ivan@example.com"


def _key(client):
    return client.post("/admin/api-keys", json={"name": "a"}, headers=ADMIN).json()["key"]


def _seed_email(client):
    # в in-memory make_client PII-правил нет (в проде их сидит DEFAULT_PATTERNS)
    r = client.post("/admin/pii", json={"type": "email", "regex": r"[\w.+-]+@[\w-]+\.[\w.-]+"},
                    headers=ADMIN)
    assert r.status_code == 200, r.text


def test_default_no_deanonymize_no_id():
    client, _ = make_client()
    _seed_email(client)
    h = {"X-API-Key": _key(client)}

    a = client.post("/v1/anonymize", json={"text": TEXT}, headers=h).json()
    assert a["id"] is None                       # по умолчанию mapping не хранится
    assert "ivan@example.com" not in a["text"]   # но анонимизация произошла


def test_deanonymize_true_stores_and_restores():
    client, _ = make_client()
    _seed_email(client)
    h = {"X-API-Key": _key(client)}

    a = client.post("/v1/anonymize", json={"text": TEXT, "deanonymize": True}, headers=h).json()
    assert a["id"] is not None

    d = client.post("/v1/deanonymize", json={"id": a["id"], "text": a["text"]}, headers=h).json()
    assert "ivan@example.com" in d["text"]


def test_deanonymize_true_without_redis_raises_503():
    client, _ = make_client()
    _seed_email(client)
    client.app.state.store.ping = lambda: False  # Redis "недоступен"
    h = {"X-API-Key": _key(client)}

    r = client.post("/v1/anonymize", json={"text": TEXT, "deanonymize": True}, headers=h)
    assert r.status_code == 503

    # без флага (дефолт) Redis не нужен — работает и при "недоступном" Redis
    ok = client.post("/v1/anonymize", json={"text": TEXT}, headers=h)
    assert ok.status_code == 200 and ok.json()["id"] is None


def test_batch_deanonymize_true_without_redis_raises_503():
    client, _ = make_client()
    _seed_email(client)
    client.app.state.store.ping = lambda: False
    h = {"X-API-Key": _key(client)}

    r = client.post("/v1/anonymize/batch",
                    json={"texts": [TEXT], "deanonymize": True}, headers=h)
    assert r.status_code == 503
