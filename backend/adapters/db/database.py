"""Фасад БД: собирает репозитории, инициализирует схему (миграции) и сиды."""

import logging

from sqlalchemy import select, text

from backend.adapters.db.models import (
    ApiKey,
    NsfwDictionary,
    PiiRule,
    RelevantCategory,
    Setting,
)
from backend.adapters.db.repositories import (
    SqlCrudRepository,
    SqlRunLogRepository,
    SqlVersionStore,
)
from backend.adapters.db.session import SessionLocal, engine
from backend.adapters.migrations import run_migrations
from backend.domain.detectors import NsfwDetector, RelevantDetector
from backend.domain.detectors.pii.patterns import DEFAULT_PATTERNS

log = logging.getLogger("db")

_SEED_LOCK_KEY = 918273645


class SqlDatabase:
    """Сборка SQL-реализаций портов в один объект для удобной проводки.

    Сам по себе портом не является — это композиция: держит per-module CRUD
    (один и тот же класс с разными моделями), версию и логи. Переезд на другую
    БД — три новых реализации портов и аналогичный фасад.
    """

    def __init__(self):
        self.pii = SqlCrudRepository(
            PiiRule, updatable=("type", "regex", "enabled"), order_by=(PiiRule.type, PiiRule.id)
        )
        self.nsfw = SqlCrudRepository(NsfwDictionary, updatable=("name", "text", "enabled"))
        self.relevant = SqlCrudRepository(
            RelevantCategory,
            updatable=("type", "text", "enabled"),
            order_by=(RelevantCategory.type,),
        )
        self.api_keys = SqlCrudRepository(
            ApiKey,
            updatable=("name", "enabled", "rate_limit_per_min"),
            order_by=(ApiKey.id,),
        )
        self.version = SqlVersionStore()
        self.runlog = SqlRunLogRepository()

    def ping(self) -> bool:
        """Проверка живости БД (для readiness-пробы). Бросает при недоступности."""
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True

    def init(self) -> None:
        wait_for_db()
        # Advisory-lock: только один воркер мигрирует/сидит, остальные ждут —
        # иначе параллельная инициализация гонится на создании таблиц.
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _SEED_LOCK_KEY})
            try:
                run_migrations(engine)
                self._seed_if_empty()
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _SEED_LOCK_KEY})
                conn.commit()

    def _seed_if_empty(self) -> None:
        """Первичное наполнение: встроенные PII-регулярки, NSFW-словарь,
        relevant-категории и стартовая версия конфига."""
        with SessionLocal() as s:
            if not s.scalar(select(PiiRule).limit(1)):
                for pattern in DEFAULT_PATTERNS:
                    s.add(PiiRule(type=pattern.name.upper(), regex=pattern.regex, enabled=True))

            if not s.scalar(select(NsfwDictionary).limit(1)):
                builtin_words = "\n".join(sorted(NsfwDetector.load_builtin_words()))
                s.add(NsfwDictionary(name="Маты RU+EN", text=builtin_words, enabled=True))

            if not s.scalar(select(RelevantCategory).limit(1)):
                for category, phrases in RelevantDetector.load_chitchat_files().items():
                    s.add(RelevantCategory(type=category, text="\n".join(phrases), enabled=True))

            if not s.get(Setting, "rules_version"):
                s.add(Setting(key="rules_version", value="1"))
            s.commit()


def wait_for_db(attempts: int = 30, delay: float = 1.0):
    """Ждём готовности БД (Postgres может подниматься дольше нашего сервиса)."""
    import time

    last = None
    for _ in range(attempts):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return
        except Exception as e:  # connection refused и т.п.
            last = e
            time.sleep(delay)
    raise RuntimeError(f"БД недоступна после {attempts} попыток: {last}")
