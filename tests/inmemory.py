"""In-memory реализации портов + сборка приложения для API-тестов.

Позволяет крутить полноценный HTTP-стек (роутеры, auth-dependency, движок,
reload при правках) через TestClient БЕЗ Postgres/Redis — тесты гермётичны и
идут в CI. Логгер синхронный: пишет сразу, чтобы логи были видны в том же тесте.
"""

import datetime as dt
import itertools
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.adapters.rate_limit import InMemoryRateLimiter
from backend.adapters.store import InMemoryMappingStore
from backend.engine import GuardEngine
from backend.entrypoints.app import create_app
from backend.entrypoints.detectors.auth import load_api_keys
from backend.ports.crud_repository import CrudRepository
from backend.ports.runlog_repository import RunLogRepository
from backend.ports.settings_store import SettingsStore
from backend.ports.version_store import VersionStore


class InMemoryCrud(CrudRepository):
    def __init__(self):
        self._rows: dict[int, dict] = {}
        self._seq = itertools.count(1)

    @staticmethod
    def _row(row_id, data):
        return SimpleNamespace(id=row_id, **data)

    def list(self):
        return [self._row(i, d) for i, d in sorted(self._rows.items())]

    def list_page(self, limit, offset=0):
        return self.list()[max(offset, 0) : max(offset, 0) + limit]

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


class InMemorySettings(SettingsStore):
    def __init__(self):
        self._d: dict[str, str] = {}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


class InMemoryRunLog(RunLogRepository):
    def __init__(self):
        self._logs: list[SimpleNamespace] = []
        self._seq = itertools.count(1)

    def write_run_logs(self, batch):
        for rec in batch:
            self._logs.append(SimpleNamespace(id=next(self._seq), **rec))

    def query_run_logs(self, module=None, limit=100, offset=0, meta_key=None, meta_value=None):
        rows = list(reversed(self._logs))  # новые сверху
        if module:
            rows = [r for r in rows if r.module == module]
        if meta_key:

            def ok(r):
                m = r.meta or {}
                return meta_key in m and (meta_value is None or str(m[meta_key]) == meta_value)

            rows = [r for r in rows if ok(r)]
        return rows[max(offset, 0) : max(offset, 0) + limit]

    def run_log_meta_keys(self):
        keys = set()
        for r in self._logs:
            if r.meta:
                keys.update(r.meta.keys())
        return sorted(keys)

    def run_log_stats(self, since, bucket_seconds):
        import json
        from collections import defaultdict

        rows = [r for r in self._logs if r.created_at >= since]

        def detected(r):
            out = json.loads(r.output)
            if r.module == "relevant":  # сработка = пойман чит-чат
                return out.get("RELEVANT") is False
            return out.get(f"{r.module.upper()}_DETECT") is True

        by_module = defaultdict(list)
        for r in rows:
            by_module[r.module].append(r)
        modules = []
        for module in sorted(by_module):
            ms = sorted(x.duration_ms for x in by_module[module])
            modules.append(
                {
                    "module": module,
                    "runs": len(ms),
                    "detections": sum(detected(x) for x in by_module[module]),
                    "avg_ms": round(sum(ms) / len(ms), 2),
                    "p95_ms": round(ms[max(0, int(len(ms) * 0.95) - 1)], 2),
                }
            )

        buckets = defaultdict(lambda: [0, 0])
        for r in rows:
            ts = dt.datetime.fromtimestamp(
                r.created_at.timestamp() // bucket_seconds * bucket_seconds
            )
            buckets[ts][0] += 1
            buckets[ts][1] += detected(r)
        timeline = [
            {"ts": ts.isoformat(), "runs": v[0], "detections": v[1]}
            for ts, v in sorted(buckets.items())
        ]

        key_runs = defaultdict(int)
        for r in rows:
            if r.meta and r.meta.get("api_key"):
                key_runs[r.meta["api_key"]] += 1
        top_keys = [
            {"name": k, "runs": n} for k, n in sorted(key_runs.items(), key=lambda kv: -kv[1])[:5]
        ]

        cls_counts = defaultdict(int)
        for r in rows:
            if r.module != "pii":
                continue
            for d in json.loads(r.output).get("data") or []:
                cls_counts[d["class"]] += 1
        pii_classes = [
            {"class": c, "count": n}
            for c, n in sorted(cls_counts.items(), key=lambda kv: -kv[1])[:5]
        ]

        return {
            "modules": modules,
            "timeline": timeline,
            "top_keys": top_keys,
            "pii_classes": pii_classes,
        }

    def delete_run_logs_before(self, cutoff):
        before = len(self._logs)
        self._logs = [r for r in self._logs if r.created_at >= cutoff]
        return before - len(self._logs)

    def run_log_metrics(self, since):
        import json
        from collections import defaultdict

        def detected(r):
            out = json.loads(r.output)
            if r.module == "relevant":
                return out.get("RELEVANT") is False
            return out.get(f"{r.module.upper()}_DETECT") is True

        agg = defaultdict(lambda: [0, 0])  # module -> [runs, detections]
        for r in self._logs:
            if r.created_at >= since:
                agg[r.module][0] += 1
                agg[r.module][1] += bool(detected(r))
        modules = [{"module": m, "runs": v[0], "detections": v[1]} for m, v in sorted(agg.items())]
        return {"total": sum(m["runs"] for m in modules), "modules": modules}


class SyncRunLogger:
    """Замена RunLogger для тестов: пишет синхронно (без очереди/потока)."""

    def __init__(self, repo):
        self._repo = repo

    def log(self, module, input_text, output, duration_ms, meta=None, detected=False):
        self._repo.write_run_logs(
            [
                {
                    "created_at": dt.datetime.utcnow(),
                    "module": module,
                    "input_text": input_text,
                    "output": output,
                    "duration_ms": duration_ms,
                    "detected": detected,
                    "meta": meta or None,
                }
            ]
        )


def build_app():
    """Собрать (app, repo) на in-memory зависимостях, без lifespan (БД/Redis не
    поднимаются — состояние ставим руками). repo — SimpleNamespace для инспекции
    в тестах. Предпочтительная точка входа для фикстур: обернуть в `with TestClient`."""
    repo = SimpleNamespace(
        pii=InMemoryCrud(),
        nsfw=InMemoryCrud(),
        relevant=InMemoryCrud(),
        api_keys=InMemoryCrud(),
        version=InMemoryVersion(),
        settings=InMemorySettings(),
        runlog=InMemoryRunLog(),
        ping=lambda: True,  # in-memory БД всегда «жива» (для health/ready-проб)
    )
    app = create_app()
    app.state.repo = repo
    app.state.guard = GuardEngine(
        repo.pii, repo.nsfw, repo.relevant, repo.version, repo.settings
    )
    app.state.store = InMemoryMappingStore()
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.api_keys = load_api_keys(repo.api_keys)
    app.state.runlog = SyncRunLogger(repo.runlog)
    return app, repo


def make_client():
    """(client, repo) без with-контекста. В новых тестах предпочитай фикстуры
    `client`/`repo` из conftest — они дают teardown и очистку dependency_overrides."""
    app, repo = build_app()
    return TestClient(app), repo
