"""API-тесты админки и детекшна через TestClient на in-memory зависимостях.

Немного, но по делу: покрывают то, что легко сломать при доработках —
авторизацию, жизненный цикл ключей, аудит по ключам + фильтрацию логов и
главное поведение «добавил словарь/категорию → детектор их подхватил».
"""

import pytest
from inmemory import make_client

ADMIN = {"X-Admin-Token": "admin"}


@pytest.fixture
def ctx():
    client, repo = make_client()
    return client, repo


def _issue_key(client, name="bot"):
    r = client.post("/admin/api-keys", json={"name": name}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["key"]


# --- auth --------------------------------------------------------------------
def test_detect_requires_valid_api_key(ctx):
    client, _ = ctx
    assert client.post("/detect/nsfw", json={"text": "привет"}).status_code == 401
    assert client.post("/detect/nsfw", json={"text": "привет"},
                       headers={"X-API-Key": "gk_bogus"}).status_code == 401

    key = _issue_key(client)
    ok = client.post("/detect/nsfw", json={"text": "привет"}, headers={"X-API-Key": key})
    assert ok.status_code == 200
    assert ok.json()["NSFW_DETECT"] is False


def test_admin_endpoints_require_admin_token(ctx):
    client, _ = ctx
    assert client.get("/admin/nsfw").status_code == 401
    assert client.get("/admin/nsfw", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.get("/admin/nsfw", headers=ADMIN).status_code == 200


# --- жизненный цикл ключей ---------------------------------------------------
def test_api_key_issuance_and_revocation(ctx):
    client, _ = ctx
    created = client.post("/admin/api-keys", json={"name": "support"}, headers=ADMIN).json()
    key = created["key"]
    assert key.startswith("gk_")

    # в списке — только prefix, сырой ключ не отдаётся никогда
    listed = client.get("/admin/api-keys", headers=ADMIN).json()["keys"]
    row = next(k for k in listed if k["id"] == created["id"])
    assert "key" not in row and row["prefix"] and key.startswith(row["prefix"])

    assert client.post("/detect/pii", json={"text": "x"}, headers={"X-API-Key": key}).status_code == 200

    # отзыв -> ключ перестаёт пускать
    assert client.delete(f"/admin/api-keys/{created['id']}", headers=ADMIN).status_code == 200
    assert client.post("/detect/pii", json={"text": "x"}, headers={"X-API-Key": key}).status_code == 401


# --- аудит по ключам + фильтрация логов --------------------------------------
def test_logs_capture_api_key_and_filter_by_it(ctx):
    client, _ = ctx
    ka = _issue_key(client, "logbot-a")
    kb = _issue_key(client, "logbot-b")
    for _ in range(3):
        client.post("/detect/pii", json={"text": "a@b.com"}, headers={"X-API-Key": ka})
    for _ in range(2):
        client.post("/detect/pii", json={"text": "c@d.com"}, headers={"X-API-Key": kb})

    a = client.get("/admin/logs", params={"module": "pii", "meta_key": "api_key",
                                          "meta_value": "logbot-a"}, headers=ADMIN).json()["logs"]
    b = client.get("/admin/logs", params={"module": "pii", "meta_key": "api_key",
                                          "meta_value": "logbot-b"}, headers=ADMIN).json()["logs"]
    assert len(a) == 3 and {r["meta"]["api_key"] for r in a} == {"logbot-a"}
    assert len(b) == 2 and {r["meta"]["api_key"] for r in b} == {"logbot-b"}

    keys = client.get("/admin/logs/meta-keys", headers=ADMIN).json()["keys"]
    assert "api_key" in keys


# --- главное: добавил через API -> детектор подхватил ------------------------
def test_added_nsfw_dictionary_is_detected(ctx):
    client, _ = ctx
    key = _issue_key(client)
    word = "плохоеслово"

    # до добавления слово не банится
    before = client.post("/detect/nsfw", json={"text": word}, headers={"X-API-Key": key}).json()
    assert before["NSFW_DETECT"] is False

    r = client.post("/admin/nsfw", json={"name": "my-dict", "text": word}, headers=ADMIN)
    assert r.status_code == 200

    after = client.post("/detect/nsfw", json={"text": f"это {word} тут"},
                        headers={"X-API-Key": key}).json()
    assert after["NSFW_DETECT"] is True
    # постороннее слово по-прежнему чистое
    assert client.post("/detect/nsfw", json={"text": "это хорошо"},
                       headers={"X-API-Key": key}).json()["NSFW_DETECT"] is False


def test_added_relevant_category_is_detected(ctx):
    client, _ = ctx
    key = _issue_key(client)
    client.post("/admin/relevant", json={"type": "smalltalk", "text": "привет как дела"},
                headers=ADMIN)

    res = client.post("/detect/relevant", json={"text": "привет как дела"},
                      headers={"X-API-Key": key}).json()
    assert res["RELEVANT"] is False        # полностью совпало -> это чит-чат
    assert res["category"] == "smalltalk"


# --- статистика дашборда ------------------------------------------------------
def test_stats_aggregates_runs_detections_and_tops(ctx):
    client, _ = ctx
    key = _issue_key(client, "statbot")
    h = {"X-API-Key": key}
    # in-memory репозитории пустые (без встроенных сидов) — заводим PII-правила
    # через админку, заодно проверяя цепочку «добавил правило -> детектит»
    client.post("/admin/pii", json={"type": "PHONE", "regex": r"\+7\d{10}"}, headers=ADMIN)
    client.post("/admin/pii", json={"type": "EMAIL", "regex": r"[\w.+-]+@[\w-]+\.\w+"},
                headers=ADMIN)
    client.post("/admin/relevant", json={"type": "greeting", "text": "привет как дела"},
                headers=ADMIN)
    # 2 pii-запуска с находками (phone+email и phone), 1 без; nsfw без детекта;
    # relevant: чит-чат (сработка = RELEVANT false) и запрос по делу
    client.post("/detect/pii", json={"text": "тел +79161234567, почта a@b.com"}, headers=h)
    client.post("/detect/pii", json={"text": "тел +79161234567"}, headers=h)
    client.post("/detect/pii", json={"text": "просто текст"}, headers=h)
    client.post("/detect/nsfw", json={"text": "привет"}, headers=h)
    client.post("/detect/relevant", json={"text": "привет как дела"}, headers=h)
    client.post("/detect/relevant", json={"text": "как настроить оплату счетов"}, headers=h)

    s = client.get("/admin/stats", params={"period": "1h"}, headers=ADMIN).json()

    pii = next(m for m in s["modules"] if m["module"] == "pii")
    nsfw = next(m for m in s["modules"] if m["module"] == "nsfw")
    rel = next(m for m in s["modules"] if m["module"] == "relevant")
    assert (pii["runs"], pii["detections"]) == (3, 2)
    assert (nsfw["runs"], nsfw["detections"]) == (1, 0)
    assert (rel["runs"], rel["detections"]) == (2, 1)  # чит-чат = сработка гуарда
    assert pii["avg_ms"] >= 0 and pii["p95_ms"] >= 0  # поля присутствуют

    # таймлайн покрывает все запуски
    assert sum(t["runs"] for t in s["timeline"]) == 6
    assert sum(t["detections"] for t in s["timeline"]) == 3

    # топ ключей и классы PII
    assert s["top_keys"][0]["name"] == "statbot" and s["top_keys"][0]["runs"] == 6
    classes = {c["class"]: c["count"] for c in s["pii_classes"]}
    assert classes.get("phone") == 2 and classes.get("email") == 1

    # невалидный период отклоняется
    assert client.get("/admin/stats", params={"period": "5y"}, headers=ADMIN).status_code == 400
    # и всё это — под админ-токеном
    assert client.get("/admin/stats").status_code == 401


# --- контракт GET словаря (нужен UI для редактирования) ----------------------
def test_nsfw_get_returns_text_while_list_hides_it(ctx):
    client, _ = ctx
    created = client.post("/admin/nsfw", json={"name": "d", "text": "раз два три"},
                          headers=ADMIN).json()
    assert "text" not in created and created["word_count"] == 3

    full = client.get(f"/admin/nsfw/{created['id']}", headers=ADMIN).json()
    assert full["text"] == "раз два три" and full["word_count"] == 3

    listed = client.get("/admin/nsfw", headers=ADMIN).json()["dicts"]
    assert all("text" not in d for d in listed)  # список не тащит текст
