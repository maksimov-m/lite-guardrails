"""ORM-модели (таблицы). Только схема — никакой логики доступа,
она в repositories.py."""

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
    # Персональный лимит запросов в минуту. NULL — глобальный дефолт из конфига.
    rate_limit_per_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
