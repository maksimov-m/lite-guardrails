"""SQL-адаптер: модели (models), подключение (session), реализации портов
(repositories) и фасад (database). Публичные имена реэкспортируются здесь,
чтобы внешний код импортировал просто `from src.adapters.db import ...`."""

from src.adapters.db.database import SqlDatabase, wait_for_db
from src.adapters.db.models import (
    ApiKey,
    Base,
    NsfwDictionary,
    PiiRule,
    RelevantCategory,
    RunLog,
    Setting,
)
from src.adapters.db.repositories import (
    SqlCrudRepository,
    SqlRunLogRepository,
    SqlVersionStore,
)
from src.adapters.db.session import SessionLocal, engine

__all__ = [
    "ApiKey",
    "Base",
    "NsfwDictionary",
    "PiiRule",
    "RelevantCategory",
    "RunLog",
    "Setting",
    "SessionLocal",
    "SqlCrudRepository",
    "SqlDatabase",
    "SqlRunLogRepository",
    "SqlVersionStore",
    "engine",
    "wait_for_db",
]
