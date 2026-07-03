"""Тесты /metrics: чистый форматтер Prometheus + HTTP-эндпоинт.

Проверяем то, что легко сломать: корректность формата (Prometheus строгий к
синтаксису), математику detections/no_detections, что счётчики отражают реальные
прогоны, что кэш реально кэширует, и что флаг METRICS_ENABLED выключает ручку.
"""

from backend.config import settings
from backend.entrypoints.metrics import CONTENT_TYPE, render_prometheus


def _parse(text):
    """Prometheus-текст -> {'имя{labels}': value} по строкам-сэмплам (без #-комментов)."""
    out = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            key, _, val = line.rpartition(" ")
            out[key] = float(val)
    return out


def _add_nsfw_word(client, admin_headers, word):
    r = client.post("/admin/nsfw", json={"name": "t", "text": word}, headers=admin_headers)
    assert r.status_code == 200, r.text


# --- чистый форматтер --------------------------------------------------------
def test_render_shape_and_math():
    snap = {
        "total": 5,
        "modules": [
            {"module": "nsfw", "runs": 3, "detections": 2},
            {"module": "pii", "runs": 2, "detections": 0},
        ],
    }

    m = _parse(render_prometheus(snap, window_seconds=86400))

    assert m["guardrails_requests_total"] == 5
    assert m['guardrails_module_requests{module="nsfw"}'] == 3
    assert m['guardrails_module_detections{module="nsfw"}'] == 2
    # no_detections = runs - detections
    assert m['guardrails_module_no_detections{module="nsfw"}'] == 1
    assert m['guardrails_module_no_detections{module="pii"}'] == 2
    assert m["guardrails_metrics_window_seconds"] == 86400


def test_render_always_emits_all_modules_with_zeros():
    """Даже если модуль не прогонялся — серия есть (иначе в Grafana пропадает линия)."""
    m = _parse(render_prometheus({"total": 0, "modules": []}, 60))

    for mod in ("pii", "nsfw", "relevant"):
        assert m[f'guardrails_module_requests{{module="{mod}"}}'] == 0
        assert m[f'guardrails_module_detections{{module="{mod}"}}'] == 0


def test_render_has_help_and_type_headers():
    """Prometheus парсит HELP/TYPE — без них метрика без метаданных."""
    text = render_prometheus({"total": 0, "modules": []}, 60)

    for name in (
        "guardrails_requests_total",
        "guardrails_module_requests",
        "guardrails_module_detections",
        "guardrails_module_no_detections",
    ):
        assert f"# HELP {name} " in text
        assert f"# TYPE {name} gauge" in text


# --- HTTP-эндпоинт -----------------------------------------------------------
def test_metrics_reflect_real_runs(client, admin_headers, auth_headers):
    client.app.state.metrics_cache = None  # свежий старт
    _add_nsfw_word(client, admin_headers, "плохое")

    # 2 прогона nsfw: один со сработкой (запрещённое слово), один без
    assert (
        client.post("/v1/detect/nsfw", json={"text": "плохое"}, headers=auth_headers).json()[
            "NSFW_DETECT"
        ]
        is True
    )
    assert (
        client.post("/v1/detect/nsfw", json={"text": "привет"}, headers=auth_headers).json()[
            "NSFW_DETECT"
        ]
        is False
    )
    # 1 прогон relevant
    client.post("/v1/detect/relevant", json={"text": "привет"}, headers=auth_headers)

    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"] == CONTENT_TYPE
    m = _parse(r.text)

    assert m['guardrails_module_requests{module="nsfw"}'] == 2
    assert m['guardrails_module_detections{module="nsfw"}'] == 1
    assert m['guardrails_module_no_detections{module="nsfw"}'] == 1
    assert m['guardrails_module_requests{module="relevant"}'] == 1
    assert m["guardrails_requests_total"] == 3


def test_metrics_are_cached_until_invalidated(client, admin_headers, auth_headers):
    client.app.state.metrics_cache = None
    _add_nsfw_word(client, admin_headers, "плохое")

    client.post("/v1/detect/nsfw", json={"text": "привет"}, headers=auth_headers)
    first = _parse(client.get("/metrics").text)
    assert first['guardrails_module_requests{module="nsfw"}'] == 1

    # ещё прогон, но в пределах окна кэша -> ответ прежний (БД не перечитываем)
    client.post("/v1/detect/nsfw", json={"text": "привет"}, headers=auth_headers)
    cached = _parse(client.get("/metrics").text)
    assert cached['guardrails_module_requests{module="nsfw"}'] == 1

    # сброс кэша -> актуальные цифры
    client.app.state.metrics_cache = None
    fresh = _parse(client.get("/metrics").text)
    assert fresh['guardrails_module_requests{module="nsfw"}'] == 2


def test_metrics_disabled_returns_404(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", False)

    assert client.get("/metrics").status_code == 404
