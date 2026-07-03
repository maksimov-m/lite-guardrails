"""SQL-реализации портов (CRUD, версия конфига, логи прогонов).

Разложены по модулям пакета (crud / version / runlog); здесь — реэкспорт,
чтобы внешний импорт `from backend.adapters.db.repositories import ...` не менялся.
Схема таблиц — в models.py, подключение — в session.py."""

from backend.adapters.db.repositories.crud import SqlCrudRepository
from backend.adapters.db.repositories.runlog import SqlRunLogRepository
from backend.adapters.db.repositories.settings import SqlSettingsStore
from backend.adapters.db.repositories.version import SqlVersionStore

__all__ = [
    "SqlCrudRepository",
    "SqlRunLogRepository",
    "SqlSettingsStore",
    "SqlVersionStore",
]
