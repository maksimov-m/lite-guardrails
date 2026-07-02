"""SQL-реализации портов (CRUD, версия конфига, логи прогонов).
Схема таблиц — в models.py, подключение — в session.py."""

import datetime as dt

from sqlalchemy import desc, select, text

from src.adapters.db.models import RunLog, Setting
from src.adapters.db.session import SessionLocal
from src.ports.crud_repository import CrudRepository
from src.ports.runlog_repository import RunLogRepository
from src.ports.version_store import VersionStore


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

    def run_log_stats(self, since: dt.datetime, bucket_seconds: int) -> dict:
        """Агрегаты для дашборда. Все запросы отсечены по created_at (индекс),
        поэтому нагрузка не зависит от размера всей таблицы — только от окна.
        Детекция = гуард сработал: для pii/nsfw это <MODULE>_DETECT = true,
        для relevant — RELEVANT = false (пойман чит-чат/нерелевантное)."""
        detect_flag = (
            "CASE WHEN module = 'relevant' "
            "THEN ((output::jsonb) ->> 'RELEVANT')::boolean IS FALSE "
            "ELSE ((output::jsonb) ->> (upper(module) || '_DETECT'))::boolean IS TRUE END"
        )
        with SessionLocal() as s:
            modules = s.execute(
                text(
                    f"""SELECT module,
                               COUNT(*) AS runs,
                               COUNT(*) FILTER (WHERE {detect_flag}) AS detections,
                               AVG(duration_ms) AS avg_ms,
                               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
                        FROM run_logs WHERE created_at >= :since
                        GROUP BY module ORDER BY module"""
                ),
                {"since": since},
            ).all()
            timeline = s.execute(
                text(
                    f"""SELECT to_timestamp(floor(extract(epoch FROM created_at) / :bs) * :bs)
                                   AS bucket,
                               COUNT(*) AS runs,
                               COUNT(*) FILTER (WHERE {detect_flag}) AS detections
                        FROM run_logs WHERE created_at >= :since
                        GROUP BY bucket ORDER BY bucket"""
                ),
                {"since": since, "bs": bucket_seconds},
            ).all()
            top_keys = s.execute(
                text(
                    """SELECT meta->>'api_key' AS name, COUNT(*) AS runs
                       FROM run_logs
                       WHERE created_at >= :since AND meta->>'api_key' IS NOT NULL
                       GROUP BY name ORDER BY runs DESC LIMIT 5"""
                ),
                {"since": since},
            ).all()
            pii_classes = s.execute(
                text(
                    """SELECT e->>'class' AS cls, COUNT(*) AS n
                       FROM run_logs,
                            LATERAL jsonb_array_elements((output::jsonb)->'data') e
                       WHERE module = 'pii' AND created_at >= :since
                         AND jsonb_typeof((output::jsonb)->'data') = 'array'
                       GROUP BY cls ORDER BY n DESC LIMIT 5"""
                ),
                {"since": since},
            ).all()
        return {
            "modules": [
                {
                    "module": r.module,
                    "runs": r.runs,
                    "detections": r.detections,
                    "avg_ms": round(r.avg_ms or 0, 2),
                    "p95_ms": round(r.p95_ms or 0, 2),
                }
                for r in modules
            ],
            "timeline": [
                {"ts": r.bucket.isoformat(), "runs": r.runs, "detections": r.detections}
                for r in timeline
            ],
            "top_keys": [{"name": r.name, "runs": r.runs} for r in top_keys],
            "pii_classes": [{"class": r.cls, "count": r.n} for r in pii_classes],
        }
