"""Рантайм-настройки детекторов — произвольные key-value в таблице settings.
Делит таблицу с версией конфига (SqlVersionStore), но по другим ключам."""

from backend.adapters.db.models import Setting
from backend.adapters.db.session import SessionLocal
from backend.ports.settings_store import SettingsStore


class SqlSettingsStore(SettingsStore):
    def get(self, key: str, default: str | None = None) -> str | None:
        with SessionLocal() as s:
            row = s.get(Setting, key)
            return row.value if row else default

    def set(self, key: str, value: str) -> None:
        with SessionLocal() as s:
            row = s.get(Setting, key)
            if row:
                row.value = value
            else:
                s.add(Setting(key=key, value=value))
            s.commit()
