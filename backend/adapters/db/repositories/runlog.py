"""Логи прогонов: запись пачками, выборка с фильтрами, агрегаты для дашборда
и метрик, ретеншн-чистка старых записей. У run_logs свои паттерны доступа
(bulk-insert, агрегации, DELETE по времени), поэтому это отдельный репозиторий,
а не generic CRUD."""

import datetime as dt

from sqlalchemy import desc, select, text

from backend.adapters.db.models import RunLog
from backend.adapters.db.session import SessionLocal
from backend.ports.runlog_repository import RunLogRepository

# Ключ advisory-локи для retention-чистки (свой, не пересекается с сид-локой).
_CLEANUP_LOCK_KEY = 918273646


class SqlRunLogRepository(RunLogRepository):
    def write_run_logs(self, batch: list[dict]) -> None:
        with SessionLocal() as s:
            s.bulk_insert_mappings(RunLog, batch)
            s.commit()

    def query_run_logs(
        self,
        module: str | None = None,
        limit: int = 100,
        offset: int = 0,
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
            q = q.offset(max(offset, 0)).limit(min(limit, 1000))
            return list(s.scalars(q).all())

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
        Детекции считаем по столбцу `detected` (посчитан на записи) — без
        построчного парсинга output::jsonb, что кратно быстрее на больших окнах."""
        with SessionLocal() as s:
            modules = s.execute(
                text(
                    """SELECT module,
                              COUNT(*) AS runs,
                              COUNT(*) FILTER (WHERE detected) AS detections,
                              AVG(duration_ms) AS avg_ms,
                              PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
                       FROM run_logs WHERE created_at >= :since
                       GROUP BY module ORDER BY module"""
                ),
                {"since": since},
            ).all()
            timeline = s.execute(
                text(
                    """SELECT to_timestamp(floor(extract(epoch FROM created_at) / :bs) * :bs)
                                  AS bucket,
                              COUNT(*) AS runs,
                              COUNT(*) FILTER (WHERE detected) AS detections
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

    def run_log_metrics(self, since: dt.datetime) -> dict:
        with SessionLocal() as s:
            rows = s.execute(
                text(
                    """SELECT module,
                              COUNT(*) AS runs,
                              COUNT(*) FILTER (WHERE detected) AS detections
                       FROM run_logs WHERE created_at >= :since
                       GROUP BY module ORDER BY module"""
                ),
                {"since": since},
            ).all()
        modules = [{"module": r.module, "runs": r.runs, "detections": r.detections} for r in rows]
        return {"total": sum(m["runs"] for m in modules), "modules": modules}

    def delete_run_logs_before(self, cutoff: dt.datetime) -> int:
        with SessionLocal() as s:
            # Неблокирующий advisory-lock: за цикл чистит только один воркер,
            # остальные пропускают (иначе 8 параллельных DELETE по тем же строкам).
            got = s.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": _CLEANUP_LOCK_KEY}
            ).scalar()
            if not got:
                return 0
            try:
                res = s.execute(
                    text("DELETE FROM run_logs WHERE created_at < :cutoff"),
                    {"cutoff": cutoff},
                )
                s.commit()
                return res.rowcount or 0
            finally:
                s.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _CLEANUP_LOCK_KEY})
                s.commit()
