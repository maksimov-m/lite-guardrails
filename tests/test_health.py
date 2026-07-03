"""Тесты проб /live, /ready, /health.

Ключевое, что проверяем:
  - /live тупой: 200 всегда, даже если зависимости лежат (иначе кубер бы
    перезапускал здоровые поды при моргании БД);
  - /ready и /health завязаны на зависимости: 503, когда что-то недоступно, и
    сообщают, что именно;
  - happy path: всё живо -> 200.
"""

from inmemory import make_client


def _boom():
    raise RuntimeError("dependency down")


def test_live_is_dumb_and_always_ok():
    client, _ = make_client()
    # даже если БД и Redis «лежат» — liveness не должен падать
    client.app.state.repo.ping = _boom
    client.app.state.store.ping = _boom
    r = client.get("/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_ok_when_deps_up():
    client, _ = make_client()
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_ready_503_when_postgres_down():
    client, _ = make_client()
    client.app.state.repo.ping = _boom
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"] == {"postgres": False, "redis": True}


def test_ready_503_when_redis_down():
    client, _ = make_client()
    client.app.state.store.ping = _boom
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["redis"] is False


def test_health_reports_each_dependency():
    client, _ = make_client()
    ok = client.get("/health")
    assert ok.status_code == 200
    assert ok.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}

    client.app.state.store.ping = _boom
    bad = client.get("/health")
    assert bad.status_code == 503
    assert bad.json() == {"status": "degraded",
                          "checks": {"postgres": "ok", "redis": "down"}}
