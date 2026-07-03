"""Лимит длины поля text (settings.max_text_length / env MAX_TEXT_LENGTH).

Ввод длиннее лимита отклоняется с 422 ещё до детекции — защита от DoS большим
вводом и смягчение ReDoS. Граница берётся из настроек, чтобы тест не отставал
от значения по умолчанию.
"""

from backend.config import settings

LIMIT = settings.max_text_length


def test_text_at_limit_accepted(client, auth_headers):
    r = client.post("/v1/detect/pii", headers=auth_headers, json={"text": "a" * LIMIT})

    assert r.status_code == 200


def test_text_over_limit_rejected(client, auth_headers):
    r = client.post("/v1/detect/pii", headers=auth_headers, json={"text": "a" * (LIMIT + 1)})

    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "string_too_long"


def test_batch_item_over_limit_rejected(client, auth_headers):
    r = client.post(
        "/v1/detect/pii/batch",
        headers=auth_headers,
        json={"texts": ["ok", "a" * (LIMIT + 1)]},
    )

    assert r.status_code == 422


def test_anonymize_over_limit_rejected(client, auth_headers):
    r = client.post("/v1/anonymize", headers=auth_headers, json={"text": "a" * (LIMIT + 1)})

    assert r.status_code == 422
