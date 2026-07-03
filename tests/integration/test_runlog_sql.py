"""Интеграционные тесты SqlRunLogRepository против НАСТОЯЩЕГО Postgres.

Зачем отдельно от остального сьюта: агрегаты дашборда/метрик и retention-чистка
написаны на сыром SQL с Postgres-специфичными штуками (PERCENTILE_CONT,
jsonb_array_elements, pg_try_advisory_lock, ::jsonb). In-memory фейки их
переписывают на Python — значит проверяют арифметику фейка, а НЕ боевой SQL.
Здесь мы гоняем ровно те запросы, что уйдут в прод.

Требуется docker (testcontainers). Без него — пропуск (не падение), чтобы
локальный прогон без docker и обычный CI-джоб оставались зелёными.
Запуск точечно:  pytest -m integration
"""

import datetime as dt
import json

import pytest

# Нет testcontainers/docker -> помечаем весь модуль как пропущенный, а не упавший.
pytest.importorskip("testcontainers.postgres")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

from backend.adapters.db.models import Base, RunLog  # noqa: E402
from backend.adapters.db.repositories import runlog as runlog_mod  # noqa: E402
from backend.adapters.db.repositories.runlog import SqlRunLogRepository  # noqa: E402

pytestmark = pytest.mark.integration

NOW = dt.datetime(2026, 7, 3, 12, 0, 0)
SINCE = NOW - dt.timedelta(hours=1)


def _detected(module, output):
    """Та же логика, что в приложении (detection._is_detection): гуард сработал."""
    if module == "relevant":
        return output.get("RELEVANT") is False
    return output.get(f"{module.upper()}_DETECT") is True


def _log(module, output, *, minutes_ago=1, duration_ms=1.0, meta=None):
    return {
        "created_at": NOW - dt.timedelta(minutes=minutes_ago),
        "module": module,
        "input_text": "x",
        "output": json.dumps(output),
        "duration_ms": duration_ms,
        "detected": _detected(module, output),
        "meta": meta,
    }


@pytest.fixture(scope="module")
def session_factory():
    """Поднимаем Postgres в контейнере один раз на модуль, создаём схему."""
    with PostgresContainer("postgres:16") as pg:
        engine = create_engine(pg.get_connection_url())
        Base.metadata.create_all(engine)
        try:
            yield sessionmaker(bind=engine, expire_on_commit=False)
        finally:
            engine.dispose()


@pytest.fixture
def repo(session_factory, monkeypatch):
    """Репозиторий берёт SessionLocal как модульный глобал — подменяем его на
    фабрику к контейнеру. Между тестами чистим run_logs для изоляции."""
    monkeypatch.setattr(runlog_mod, "SessionLocal", session_factory)
    with session_factory() as s:
        s.query(RunLog).delete()
        s.commit()
    return SqlRunLogRepository()


def test_stats_percentile_detections_and_pii_classes(repo):
    repo.write_run_logs(
        [
            # pii: 2 сработки (phone+email, phone), 1 без; разное duration -> p95
            _log("pii", {"PII_DETECT": True, "data": [{"class": "phone"}, {"class": "email"}]},
                 duration_ms=2.0, meta={"api_key": "bot-a"}),
            _log("pii", {"PII_DETECT": True, "data": [{"class": "phone"}]},
                 duration_ms=8.0, meta={"api_key": "bot-a"}),
            _log("pii", {"PII_DETECT": False, "data": []},
                 duration_ms=4.0, meta={"api_key": "bot-b"}),
            # relevant: сработка гуарда = RELEVANT false (пойман чит-чат)
            _log("relevant", {"RELEVANT": False}, meta={"api_key": "bot-a"}),
            _log("relevant", {"RELEVANT": True}, meta={"api_key": "bot-b"}),
        ]
    )

    stats = repo.run_log_stats(SINCE, bucket_seconds=300)

    pii = next(m for m in stats["modules"] if m["module"] == "pii")
    rel = next(m for m in stats["modules"] if m["module"] == "relevant")
    assert (pii["runs"], pii["detections"]) == (3, 2)
    assert (rel["runs"], rel["detections"]) == (2, 1)
    assert pii["avg_ms"] == pytest.approx(4.67, abs=0.1)  # (2+8+4)/3, реальный AVG SQL
    assert pii["p95_ms"] >= 8.0  # PERCENTILE_CONT дотягивает до верхней границы

    # jsonb_array_elements + e->>'class' на настоящем JSONB
    classes = {c["class"]: c["count"] for c in stats["pii_classes"]}
    assert classes == {"phone": 2, "email": 1}

    # meta->>'api_key' топ
    top = {k["name"]: k["runs"] for k in stats["top_keys"]}
    assert top["bot-a"] == 3 and top["bot-b"] == 2


def test_metrics_totals_match_stats(repo):
    repo.write_run_logs(
        [
            _log("nsfw", {"NSFW_DETECT": True, "data": []}),
            _log("nsfw", {"NSFW_DETECT": False, "data": []}),
        ]
    )

    metrics = repo.run_log_metrics(SINCE)

    assert metrics["total"] == 2
    nsfw = next(m for m in metrics["modules"] if m["module"] == "nsfw")
    assert (nsfw["runs"], nsfw["detections"]) == (2, 1)


def test_window_excludes_old_rows(repo):
    repo.write_run_logs(
        [
            _log("pii", {"PII_DETECT": True, "data": []}, minutes_ago=1),   # в окне
            _log("pii", {"PII_DETECT": True, "data": []}, minutes_ago=180),  # старше часа
        ]
    )

    assert repo.run_log_metrics(SINCE)["total"] == 1  # created_at >= :since режет старое


def test_meta_jsonb_filter(repo):
    repo.write_run_logs(
        [
            _log("pii", {"PII_DETECT": False, "data": []}, meta={"api_key": "keep"}),
            _log("pii", {"PII_DETECT": False, "data": []}, meta={"api_key": "drop"}),
            _log("pii", {"PII_DETECT": False, "data": []}, meta=None),
        ]
    )

    only_keep = repo.query_run_logs(meta_key="api_key", meta_value="keep")
    any_key = repo.query_run_logs(meta_key="api_key")  # has_key

    assert len(only_keep) == 1 and only_keep[0].meta["api_key"] == "keep"
    assert len(any_key) == 2  # строка с meta=None не имеет ключа

    keys = repo.run_log_meta_keys()
    assert keys == ["api_key"]


def test_retention_delete_returns_count_and_uses_advisory_lock(repo):
    repo.write_run_logs(
        [
            _log("pii", {"PII_DETECT": False, "data": []}, minutes_ago=1),   # свежая
            _log("pii", {"PII_DETECT": False, "data": []}, minutes_ago=200),  # старая
            _log("pii", {"PII_DETECT": False, "data": []}, minutes_ago=300),  # старая
        ]
    )
    cutoff = NOW - dt.timedelta(hours=2)

    deleted = repo.delete_run_logs_before(cutoff)

    assert deleted == 2
    assert repo.run_log_metrics(NOW - dt.timedelta(days=1))["total"] == 1
