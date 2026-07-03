"""SQL-адаптер: модели (models), подключение (session), реализации портов
(repositories) и фасад (database). Публичные имена реэкспортируются здесь,
чтобы внешний код импортировал просто `from backend.adapters.db import ...`."""

from backend.adapters.db.database import SqlDatabase, wait_for_db
from backend.adapters.db.models import (
    ApiKey,
    Base,
    NSFWDictionary,
    PiiRule,
    RelevantCategory,
    RunLog,
    Setting,
)
from backend.adapters.db.repositories import (
    SqlCrudRepository,
    SqlRunLogRepository,
    SqlVersionStore,
)
from backend.adapters.db.session import SessionLocal, engine

__all__ = [
    "ApiKey",
    "Base",
    "NSFWDictionary",
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
