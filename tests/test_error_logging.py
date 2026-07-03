"""Непойманное исключение -> глобальный обработчик: 500 + ERROR со стектрейсом
в нашем формате (а не «тихо» и не чужим форматом uvicorn)."""

import logging

from fastapi.testclient import TestClient

from backend.entrypoints.app import create_app


def test_unhandled_exception_logs_error_and_returns_500(caplog):
    app = create_app()  # без lifespan — БД не нужна для этого маршрута

    @app.get("/_boom")
    def boom():
        raise RuntimeError("kaboom")

    # raise_server_exceptions=False -> клиент получает ответ обработчика, а не re-raise
    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="app"):
        r = client.get("/_boom")

    assert r.status_code == 500
    assert r.json() == {"detail": "internal server error"}
    errors = [rec for rec in caplog.records if rec.levelname == "ERROR"]
    assert any("unhandled exception" in rec.message for rec in errors)
    # стектрейс приложен
    assert any(rec.exc_info for rec in errors)
