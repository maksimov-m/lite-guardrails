"""Общие фикстуры для API-тестов (см. inmemory.py — in-memory реализации портов).

Здесь живёт вся тестовая «сантехника», чтобы сами тесты были короткими и по делу:
сборка приложения с teardown, админ-заголовки, выпуск API-ключей. Фикстуры
доступны во всех тестах пакета без импорта.
"""

import pytest
from fastapi.testclient import TestClient
from inmemory import build_app

from backend.config import settings

# Небоевой админ-токен: тесты НЕ должны зависеть от небезопасного дефолта "admin".
# Как только на старте появится fail-fast на admin_token == "admin", сьют не упадёт.
TEST_ADMIN_TOKEN = "test-admin-token"


@pytest.fixture(autouse=True)
def admin_token(monkeypatch):
    """Подменяем админ-токен для каждого теста. autouse: применяется везде,
    возвращает значение — чтобы admin_headers зависел от него явно (порядок)."""
    monkeypatch.setattr(settings, "admin_token", TEST_ADMIN_TOKEN)
    return TEST_ADMIN_TOKEN


@pytest.fixture
def client_repo():
    """(client, repo) на in-memory зависимостях. `with TestClient` прогоняет
    ASGI-жизненный цикл и гарантированно закрывает клиент; dependency_overrides
    чистим в teardown — утечка override между тестами это #1 источник флаки."""
    app, repo = build_app()
    with TestClient(app) as client:
        yield client, repo
    app.dependency_overrides.clear()


@pytest.fixture
def client(client_repo):
    return client_repo[0]


@pytest.fixture
def repo(client_repo):
    return client_repo[1]


@pytest.fixture
def admin_headers(admin_token):
    return {"X-Admin-Token": admin_token}


@pytest.fixture
def issue_key(client, admin_headers):
    """Фабрика: выпустить API-ключ через админку и вернуть сырой ключ.
    Использование: `key = issue_key()` или `issue_key("logbot-a")`."""

    def _issue(name="test", **body):
        r = client.post("/admin/api-keys", json={"name": name, **body}, headers=admin_headers)
        assert r.status_code == 200, r.text
        return r.json()["key"]

    return _issue


@pytest.fixture
def api_key(issue_key):
    """Один готовый ключ для типового случая «нужен любой валидный ключ»."""
    return issue_key()


@pytest.fixture
def auth_headers(api_key):
    return {"X-API-Key": api_key}
