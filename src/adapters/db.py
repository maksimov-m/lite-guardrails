import datetime as dt
import logging

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    desc,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.adapters.migrations import run_migrations
from src.config import settings
from src.domain.detectors import NsfwDetector, RelevantDetector
from src.domain.detectors.pii.patterns import DEFAULT_PATTERNS
from src.ports.crud_repository import CrudRepository
from src.ports.runlog_repository import RunLogRepository
from src.ports.version_store import VersionStore

log = logging.getLogger("db")

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

_SEED_LOCK_KEY = 918273645


class Base(DeclarativeBase):
    pass


class PiiRule(Base):
    """Одна regex-сигнатура PII. Несколько строк на один тип допустимы
    (в движке они склеиваются в один паттерн через |)."""

    __tablename__ = "pii_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    regex: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


class RunLog(Base):
    """Лог одного прогона детекции: вход, выход, время обработки."""

    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, index=True
    )
    module: Mapped[str] = mapped_column(String(16), index=True)
    input_text: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)  # JSON-строка результата
    duration_ms: Mapped[float] = mapped_column(Float)
    # Произвольные метаданные запроса (user_id, app, env...). JSONB — чтобы
    # фильтровать логи по ключу/значению прямо в SQL.
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class NsfwDictionary(Base):
    """Словарь NSFW: имя + слова одной строкой (через пробелы/переносы).
    Целиком включается/выключается."""

    __tablename__ = "nsfw_dictionaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    text: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


class RelevantCategory(Base):
    """Категория смолтока: тип + фразы (по одной на строку). Одна строка = вся категория."""

    __tablename__ = "relevant_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64), unique=True)
    text: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


class Setting(Base):
    """Простое key-value (версия конфига для reload воркеров)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256))


class ApiKey(Base):
    """API-ключ клиента детекшн-ручек. Храним только sha256-хэш ключа —
    сам ключ показывается один раз при создании. prefix — для отображения
    в админке (по нему ключ узнаётся, но не восстанавливается)."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class SqlCrudRepository(CrudRepository):
    """Один generic CRUD на SQLAlchemy — переиспользуется для всех модулей.
    Модель и список изменяемых полей задаются в конструкторе, методы общие."""

    def __init__(self, model, updatable: tuple[str, ...], order_by: tuple = ()):
        self._model = model
        self._updatable = updatable
        self._order_by = order_by or (model.id,)

    def list(self) -> list:
        with SessionLocal() as s:
            return list(s.scalars(select(self._model).order_by(*self._order_by)).all())

    def get(self, row_id: int):
        with SessionLocal() as s:
            return s.get(self._model, row_id)

    def find_by(self, field: str, value):
        with SessionLocal() as s:
            return s.scalar(select(self._model).where(getattr(self._model, field) == value))

    def create(self, **fields):
        with SessionLocal() as s:
            row = self._model(**fields)
            s.add(row)
            s.commit()
            return row

    def update(self, row_id: int, fields: dict):
        with SessionLocal() as s:
            row = s.get(self._model, row_id)
            if not row:
                return None
            for name in self._updatable:
                if fields.get(name) is not None:
                    setattr(row, name, fields[name])
            s.commit()
            return row

    def delete(self, row_id: int) -> bool:
        with SessionLocal() as s:
            row = s.get(self._model, row_id)
            if not row:
                return False
            s.delete(row)
            s.commit()
            return True


class SqlVersionStore(VersionStore):
    def get_version(self) -> int:
        with SessionLocal() as s:
            row = s.get(Setting, "rules_version")
            return int(row.value) if row else 0

    def bump_version(self) -> int:
        with SessionLocal() as s:
            row = s.get(Setting, "rules_version")
            new = (int(row.value) + 1) if row else 1
            if row:
                row.value = str(new)
            else:
                s.add(Setting(key="rules_version", value=str(new)))
            s.commit()
            return new


class SqlRunLogRepository(RunLogRepository):
    def write_run_logs(self, batch: list[dict]) -> None:
        with SessionLocal() as s:
            s.bulk_insert_mappings(RunLog, batch)
            s.commit()

    def query_run_logs(
        self,
        module: str | None = None,
        limit: int = 100,
        meta_key: str | None = None,
        meta_value: str | None = None,
    ) -> list[RunLog]:
        with SessionLocal() as s:
            q = select(RunLog).order_by(desc(RunLog.created_at))
            if module:
                q = q.where(RunLog.module == module)
            if meta_key:
                if meta_value not in (None, ""):
                    q = q.where(RunLog.meta[meta_key].astext == meta_value)
                else:
                    q = q.where(RunLog.meta.has_key(meta_key))  # noqa: W601 (JSONB ?)
            return list(s.scalars(q.limit(min(limit, 1000))).all())

    def run_log_meta_keys(self) -> list[str]:
        with SessionLocal() as s:
            rows = s.execute(
                text(
                    "SELECT DISTINCT jsonb_object_keys(meta) AS k FROM run_logs "
                    "WHERE jsonb_typeof(meta) = 'object' ORDER BY k"
                )
            ).all()
            return [r.k for r in rows]


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
            ApiKey, updatable=("name", "enabled"), order_by=(ApiKey.id,)
        )
        self.version = SqlVersionStore()
        self.runlog = SqlRunLogRepository()

    def init(self) -> None:
        wait_for_db()
        # Advisory-lock: только один воркер создаёт схему/сидит, остальные ждут —
        # иначе параллельный create_all() гонится на создании таблиц.
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
