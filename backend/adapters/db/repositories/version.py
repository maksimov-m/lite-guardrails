"""Версия конфига детекторов — счётчик в таблице settings. По нему воркеры
понимают, что правила/словари изменились, и горячо перезагружают движок."""

from backend.adapters.db.models import Setting
from backend.adapters.db.session import SessionLocal
from backend.ports.version_store import VersionStore


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
