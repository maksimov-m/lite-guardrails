"""Прогон Alembic-миграций из приложения (под advisory-lock в db.init()).

Логика stamp-or-upgrade делает переход с прежнего create_all() безболезненным:
- есть alembic_version  -> обычный upgrade до head;
- таблицы есть, а alembic_version нет -> БД создана старым create_all(); принимаем
  текущую схему за baseline (stamp), НЕ пересоздавая таблицы;
- БД пустая -> upgrade создаёт всё с нуля.
"""

import logging
import os

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from backend.config import settings

log = logging.getLogger("db")

_ALEMBIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", _ALEMBIC_DIR)
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def run_migrations(engine) -> None:
    tables = set(inspect(engine).get_table_names())
    cfg = _config()
    if "alembic_version" in tables:
        log.info("alembic: upgrade -> head")
        command.upgrade(cfg, "head")
    elif tables:
        log.info("alembic: существующая схема без версии -> stamp head (baseline)")
        command.stamp(cfg, "head")
    else:
        log.info("alembic: пустая БД -> upgrade создаёт схему")
        command.upgrade(cfg, "head")
