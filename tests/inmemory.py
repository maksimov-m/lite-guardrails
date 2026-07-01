"""In-memory реализации портов + сборка приложения для API-тестов.

Позволяет крутить полноценный HTTP-стек (роутеры, auth-dependency, движок,
reload при правках) через TestClient БЕЗ Postgres/Redis — тесты гермётичны и
идут в CI. Логгер синхронный: пишет сразу, чтобы логи были видны в том же тесте.
"""

import datetime as dt
import itertools
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.adapters.store import InMemoryMappingStore
from src.engine import GuardEngine
from src.entrypoints.app import create_app
from src.entrypoints.detectors.auth import load_api_keys
from src.ports.crud_repository import CrudRepository
from src.ports.runlog_repository import RunLogRepository
from src.ports.version_store import VersionStore


class InMemoryCrud(CrudRepository):
    def __init__(self):
        self._rows: dict[int, dict] = {}
        self._seq = itertools.count(1)

    @staticmethod
    def _row(row_id, data):
        return SimpleNamespace(id=row_id, **data)

    def list(self):
        return [self._row(i, d) for i, d in sorted(self._rows.items())]

    def get(self, row_id):
        d = self._rows.get(row_id)
        return self._row(row_id, d) if d is not None else None

    def find_by(self, field, value):
        for i, d in self._rows.items():
            if d.get(field) == value:
                return self._row(i, d)
        return None

    def create(self, **fields):
        row_id = next(self._seq)
        now = dt.datetime.utcnow()
        self._rows[row_id] = {"created_at": now, "updated_at": now, **fields}
        return self._row(row_id, self._rows[row_id])

    def update(self, row_id, fields):
        d = self._rows.get(row_id)
        if d is None:
            return None
        for k, v in fields.items():
            if v is not None:
                d[k] = v
        return self._row(row_id, d)

    def delete(self, row_id):
        return self._rows.pop(row_id, None) is not None


class InMemoryVersion(VersionStore):
    def __init__(self):
        self._v = 0

    def get_version(self):
        return self._v

    def bump_version(self):
        self._v += 1
        return self._v


class InMemoryRunLog(RunLogRepository):
    def __init__(self):
        self._logs: list[SimpleNamespace] = []
        self._seq = itertools.count(1)

    def write_run_logs(self, batch):
        for rec in batch:
            self._logs.append(SimpleNamespace(id=next(self._seq), **rec))

    def query_run_logs(self, module=None, limit=100, meta_key=None, meta_value=None):
        rows = list(reversed(self._logs))  # новые сверху
        if module:
            rows = [r for r in rows if r.module == module]
        if meta_key:
            def ok(r):
                m = r.meta or {}
                return meta_key in m and (meta_value is None or str(m[meta_key]) == meta_value)
            rows = [r for r in rows if ok(r)]
        return rows[:limit]

    def run_log_meta_keys(self):
        keys = set()
        for r in self._logs:
            if r.meta:
                keys.update(r.meta.keys())
        return sorted(keys)


class SyncRunLogger:
    """Замена RunLogger для тестов: пишет синхронно (без очереди/потока)."""

    def __init__(self, repo):
        self._repo = repo

    def log(self, module, input_text, output, duration_ms, meta=None):
        self._repo.write_run_logs([{
            "created_at": dt.datetime.utcnow(),
            "module": module,
            "input_text": input_text,
            "output": output,
            "duration_ms": duration_ms,
            "meta": meta or None,
        }])


def make_client():
    """Собрать (client, repo) на in-memory зависимостях. repo — для инспекции в тестах."""
    repo = SimpleNamespace(
        pii=InMemoryCrud(),
        nsfw=InMemoryCrud(),
        relevant=InMemoryCrud(),
        api_keys=InMemoryCrud(),
        version=InMemoryVersion(),
        runlog=InMemoryRunLog(),
    )
    app = create_app()  # без lifespan — состояние ставим руками, БД не поднимается
    app.state.repo = repo
    app.state.guard = GuardEngine(repo.pii, repo.nsfw, repo.relevant, repo.version)
    app.state.store = InMemoryMappingStore()
    app.state.api_keys = load_api_keys(repo.api_keys)
    app.state.runlog = SyncRunLogger(repo.runlog)
    return TestClient(app), repo
