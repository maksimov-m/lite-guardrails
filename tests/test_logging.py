"""Тесты логирования: structured JSON, сквозной request-id и PII-безопасность.

Главный тест — что текст пользователя НИКОГДА не попадает в stdout-логи
(в отличие от аудита run_logs, куда пишется анонимизированный текст)."""

import json
import logging

from inmemory import make_client

from backend.logging_config import _JsonFormatter, _RequestIdFilter

ADMIN = {"X-Admin-Token": "admin"}


def test_json_formatter_is_structured():
    rec = logging.makeLogRecord(
        {"name": "access", "levelname": "INFO", "levelno": logging.INFO, "msg": "request"}
    )
    rec.request_id = "rid-1"
    rec.status = 200
    out = json.loads(_JsonFormatter().format(rec))
    assert out["logger"] == "access"
    assert out["level"] == "INFO"
    assert out["request_id"] == "rid-1"
    assert out["status"] == 200


def test_request_id_echoed_and_generated():
    client, _ = make_client()
    echoed = client.get("/live", headers={"X-Request-ID": "abc123"})
    assert echoed.headers["X-Request-ID"] == "abc123"

    generated = client.get("/live")
    assert generated.headers["X-Request-ID"]
    assert generated.headers["X-Request-ID"] != "abc123"


def test_user_text_never_appears_in_logs():
    client, _ = make_client()
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            captured.append(self.format(record))

    handler = _Capture()
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    prev = root.level
    root.setLevel(logging.INFO)
    try:
        key = client.post("/admin/api-keys", json={"name": "b"}, headers=ADMIN).json()["key"]
        secret = "OCHEN_SEKRETNIY_TEXT_42"
        client.post("/v1/detect/nsfw", json={"text": secret}, headers={"X-API-Key": key})
    finally:
        root.removeHandler(handler)
        root.setLevel(prev)

    blob = "\n".join(captured)
    assert '"msg": "request"' in blob  # access-лог был записан
    assert secret not in blob  # но текст пользователя — нет
