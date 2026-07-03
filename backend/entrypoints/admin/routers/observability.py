"""Наблюдаемость: версия конфига, логи прогонов, статистика для дашборда."""

import datetime as dt

from fastapi import APIRouter, HTTPException, Request

from backend.entrypoints.admin.utils import STAT_PERIODS, db, log_out

router = APIRouter()


@router.get("/version")
def version(request: Request):
    return {
        "db_version": db(request).version.get_version(),
        "active_version": request.app.state.guard.version,
    }


@router.get("/logs")
def logs(
    request: Request,
    module: str | None = None,
    limit: int = 50,
    offset: int = 0,
    meta_key: str | None = None,
    meta_value: str | None = None,
):
    # Берём на одну строку больше запрошенного — так узнаём, есть ли ещё страница,
    # без дорогого COUNT(*) по всей таблице.
    rows = db(request).runlog.query_run_logs(
        module=module,
        limit=limit + 1,
        offset=offset,
        meta_key=meta_key,
        meta_value=meta_value,
    )
    has_more = len(rows) > limit
    return {
        "logs": [log_out(r) for r in rows[:limit]],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@router.get("/logs/meta-keys")
def logs_meta_keys(request: Request):
    """Список всех встречающихся в логах ключей metadata (для фильтра в UI)."""
    return {"keys": db(request).runlog.run_log_meta_keys()}


@router.get("/stats")
def stats(request: Request, period: str = "24h"):
    if period not in STAT_PERIODS:
        raise HTTPException(400, f"period должен быть одним из {sorted(STAT_PERIODS)}")
    window, bucket_seconds = STAT_PERIODS[period]
    since = dt.datetime.utcnow() - window
    return {"period": period, **db(request).runlog.run_log_stats(since, bucket_seconds)}
