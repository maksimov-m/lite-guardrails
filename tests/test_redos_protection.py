"""Защита от ReDoS в пользовательских PII-regex (два слоя).

Слой 1 — гейт на создании правила (validate_regex): состязательные пробы
отклоняют катастрофические паттерны с 400.
Слой 2 — рантайм-таймаут в PiiPattern.find: паттерн, проскочивший гейт (или
засеянный в БД в обход API), на живом запросе прерывается по бюджету и уходит
в fail-closed 500 — воркер не виснет.
"""

import time

from backend.domain.detectors.errors import DetectorTimeout
from backend.domain.detectors.pii.patterns.base import (
    MATCH_TIMEOUT_SECONDS,
    PiiPattern,
)

# Классический катастрофический бэктрекинг, который движок `regex` НЕ оптимизирует.
CATASTROPHIC = r"(a|a)+$"
ATTACK = "a" * 60 + "!"  # несовпадающий хвост форсирует полный перебор


# --- Слой 1: гейт на создании ------------------------------------------------
def test_gate_rejects_catastrophic_regex(client, admin_headers):
    r = client.post(
        "/admin/pii",
        headers=admin_headers,
        json={"type": "EVIL", "regex": CATASTROPHIC, "enabled": True},
    )

    assert r.status_code == 400
    assert "backtrack" in r.json()["detail"].lower() or "бэктрек" in r.json()["detail"].lower()


def test_gate_accepts_safe_regex(client, admin_headers):
    r = client.post(
        "/admin/pii",
        headers=admin_headers,
        json={"type": "EMAIL2", "regex": r"[a-z0-9._%+-]+@[a-z.-]+\.[a-z]{2,}", "enabled": True},
    )

    assert r.status_code == 200


# --- Слой 2: рантайм-таймаут -------------------------------------------------
def test_pattern_find_raises_detector_timeout_and_is_bounded():
    pattern = PiiPattern(name="evil", regex=CATASTROPHIC)

    start = time.perf_counter()
    try:
        pattern.find(ATTACK)
        raised = False
    except DetectorTimeout as exc:
        raised = True
        assert exc.pattern_name == "evil"
    elapsed = time.perf_counter() - start

    assert raised, "ожидали DetectorTimeout на катастрофическом паттерне"
    # бюджет 50 мс + накладные — прерывание, а не зависание
    assert elapsed < MATCH_TIMEOUT_SECONDS + 1.0


def test_detect_fails_closed_on_seeded_catastrophic_rule(client, repo, admin_headers):
    """Правило засеяно в обход гейта (прямо в репозиторий). На атакующем вводе
    детекция обязана вернуть 500 (fail-closed), а не зависнуть."""
    # выдаём клиентский ключ штатно, чтобы пройти require_api_key
    key = client.post(
        "/admin/api-keys", headers=admin_headers, json={"name": "victim", "rate_limit_per_min": 0}
    ).json()["key"]
    # сеем злое правило мимо API и перезагружаем движок
    repo.pii.create(type="EVIL", regex=CATASTROPHIC, enabled=True)
    repo.version.bump_version()
    client.app.state.guard.reload()

    start = time.perf_counter()
    r = client.post("/v1/detect/pii", headers={"X-API-Key": key}, json={"text": ATTACK})
    elapsed = time.perf_counter() - start

    assert r.status_code == 500
    assert elapsed < MATCH_TIMEOUT_SECONDS + 1.0
    # короткий ввод не форсирует бэктрекинг — то же злое правило отвечает нормально
    ok = client.post(
        "/v1/detect/pii", headers={"X-API-Key": key}, json={"text": "short benign text"}
    )
    assert ok.status_code == 200
