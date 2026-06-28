import datetime as dt
import os

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, String, Text, create_engine, select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://guard:guard@localhost:5432/guard",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Rule(Base):
    """Правило детекции. Универсально для всех модулей:
      pii      -> label = тип сущности (EMAIL/PHONE/...), value = regex
      nsfw     -> value = слово (label не используется)
      relevant -> label = категория (тип смолтока), value = фраза
    """
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module: Mapped[str] = mapped_column(String(16), index=True)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class RunLog(Base):
    """Лог одного прогона детекции: вход, выход, время обработки."""
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, index=True)
    module: Mapped[str] = mapped_column(String(16), index=True)
    input_text: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)        # JSON-строка результата
    duration_ms: Mapped[float] = mapped_column(Float)
    # Произвольные метаданные запроса (user_id, app, env...). JSONB — чтобы
    # фильтровать логи по ключу/значению прямо в SQL.
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Dictionary(Base):
    """Словарь для NSFW: именованный набор слов, который целиком вкл/выкл.

    builtin=True — встроенный baseline (RU+EN ~4900 слов в коде), слова в БД не
    хранятся, редактировать нельзя, только включить/выключить.
    Слова пользовательских словарей лежат в rules (module=nsfw, label=имя_словаря).
    """
    __tablename__ = "dictionaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)


class Setting(Base):
    """Простое key-value (версия конфига для reload воркеров)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256))


def wait_for_db(attempts: int = 30, delay: float = 1.0):
    """Ждём готовности БД (Postgres может подниматься дольше нашего сервиса)."""
    import time

    from sqlalchemy import text
    last = None
    for _ in range(attempts):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return
        except Exception as e:        # connection refused и т.п.
            last = e
            time.sleep(delay)
    raise RuntimeError(f"БД недоступна после {attempts} попыток: {last}")


def init_db():
    wait_for_db()
    from sqlalchemy import text
    # Advisory-lock: только один воркер создаёт схему/сидит, остальные ждут —
    # иначе параллельный create_all() гонится на создании таблиц.
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(918273645)"))
        try:
            Base.metadata.create_all(engine)
            # лёгкая миграция для уже существующих БД (create_all не делает ALTER)
            conn.execute(text(
                "ALTER TABLE run_logs ADD COLUMN IF NOT EXISTS meta JSONB"))
            conn.commit()
            _seed_if_empty()
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(918273645)"))
            conn.commit()


def get_version() -> int:
    with SessionLocal() as s:
        row = s.get(Setting, "rules_version")
        return int(row.value) if row else 0


def bump_version() -> int:
    """Увеличивает версию конфига (вызывается на Apply)."""
    with SessionLocal() as s:
        row = s.get(Setting, "rules_version")
        new = (int(row.value) + 1) if row else 1
        if row:
            row.value = str(new)
        else:
            s.add(Setting(key="rules_version", value=str(new)))
        s.commit()
        return new


def _seed_if_empty():
    """Первичное наполнение БД встроенными правилами PII и relevant.

    NSFW-словарь (~4900 слов) остаётся встроенным baseline в коде — в БД кладём
    только кастомные NSFW-слова, добавленные через админку.
    """
    from src.domain.detectors import RelevantDetector
    from src.domain.detectors.pii.patterns import DEFAULT_PATTERNS

    with SessionLocal() as s:
        # встроенный NSFW-словарь (всегда есть как переключаемый baseline)
        if not s.scalar(select(Dictionary).where(Dictionary.builtin.is_(True))):
            s.add(Dictionary(name="Маты RU+EN (встроенный)",
                             enabled=True, builtin=True))

        if not s.scalar(select(Rule).limit(1)):
            # PII: встроенные regex -> правила
            for pattern in DEFAULT_PATTERNS:
                s.add(Rule(module="pii", label=pattern.name.upper(),
                           value=pattern.regex, enabled=True))

            # relevant: фразы из файлов -> правила (label = категория)
            for category, phrases in RelevantDetector.load_chitchat_files().items():
                for phrase in phrases:
                    s.add(Rule(module="relevant", label=category,
                               value=phrase, enabled=True))

        if not s.get(Setting, "rules_version"):
            s.add(Setting(key="rules_version", value="1"))
        s.commit()
