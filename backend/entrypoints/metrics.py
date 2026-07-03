"""Экспорт метрик в формате Prometheus (`GET /metrics`).

Модель pull: Prometheus сам скрейпит эту ручку раз в N секунд и хранит историю;
Grafana строит графики. Ручка opt-in — если её никто не скрейпит, она ничего не
стоит и ни от чего внешнего не зависит.

Считаем не по счётчикам в памяти (у нас несколько воркеров — у каждого была бы
своя частичная картина), а по общей БД `run_logs`: любой воркер видит полную
картину. Чтобы частый scrape не молотил БД, ответ кэшируется на несколько секунд.

Метрики (скользящее окно `metrics_window_seconds`, тип gauge):
  guardrails_requests_total                      — всего прогонов
  guardrails_module_requests{module}             — прогонов по модулю
  guardrails_module_detections{module}           — сработок (сущности найдены)
  guardrails_module_no_detections{module}        — прогонов без сработки
  guardrails_metrics_window_seconds              — ширина окна
"""

import datetime as dt
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from backend.config import settings

router = APIRouter()

# Prometheus text exposition format v0.0.4.
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# Всегда отдаём все три модуля (даже с нулями) — так в Grafana не пропадают серии.
_KNOWN_MODULES = ("pii", "nsfw", "relevant")


def _escape(value: str) -> str:
    """Экранирование значения метки по спецификации Prometheus."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus(snapshot: dict, window_seconds: int) -> str:
    """Чистая функция: снимок из репозитория -> текст в формате Prometheus.

    snapshot: {"total": int, "modules": [{"module", "runs", "detections"}]}
    """
    by_module = {m["module"]: m for m in snapshot.get("modules", [])}
    modules = list(_KNOWN_MODULES) + [
        m for m in by_module if m not in _KNOWN_MODULES
    ]

    lines: list[str] = []

    lines += [
        "# HELP guardrails_requests_total Total detection requests in the rolling window.",
        "# TYPE guardrails_requests_total gauge",
        f"guardrails_requests_total {snapshot.get('total', 0)}",
    ]

    lines += [
        "# HELP guardrails_module_requests Detection requests per module in the rolling window.",
        "# TYPE guardrails_module_requests gauge",
    ]
    for name in modules:
        runs = by_module.get(name, {}).get("runs", 0)
        lines.append(f'guardrails_module_requests{{module="{_escape(name)}"}} {runs}')

    lines += [
        "# HELP guardrails_module_detections Requests where the guard fired (entities found).",
        "# TYPE guardrails_module_detections gauge",
    ]
    for name in modules:
        det = by_module.get(name, {}).get("detections", 0)
        lines.append(f'guardrails_module_detections{{module="{_escape(name)}"}} {det}')

    lines += [
        "# HELP guardrails_module_no_detections Requests where nothing was found.",
        "# TYPE guardrails_module_no_detections gauge",
    ]
    for name in modules:
        m = by_module.get(name, {})
        no_det = m.get("runs", 0) - m.get("detections", 0)
        lines.append(f'guardrails_module_no_detections{{module="{_escape(name)}"}} {no_det}')

    lines += [
        "# HELP guardrails_metrics_window_seconds Rolling window width for the counts above.",
        "# TYPE guardrails_metrics_window_seconds gauge",
        f"guardrails_metrics_window_seconds {window_seconds}",
    ]

    return "\n".join(lines) + "\n"


def _query_snapshot(app) -> dict:
    """Блокирующий (psycopg2) запрос к БД — вызывать в threadpool, не в event loop."""
    since = dt.datetime.utcnow() - dt.timedelta(seconds=settings.metrics_window_seconds)
    return app.state.repo.runlog.run_log_metrics(since)


async def _cached_text(app) -> str:
    """Ответ из кэша, если он свежий; иначе один запрос к БД в threadpool."""
    cache = getattr(app.state, "metrics_cache", None)
    now = time.monotonic()
    if cache and now - cache["ts"] < settings.metrics_cache_seconds:
        return cache["text"]
    snapshot = await run_in_threadpool(_query_snapshot, app)
    body = render_prometheus(snapshot, settings.metrics_window_seconds)
    app.state.metrics_cache = {"ts": now, "text": body}
    return body


@router.get("/metrics")
async def metrics(request: Request):
    if not settings.metrics_enabled:
        raise HTTPException(404, "metrics disabled")
    return PlainTextResponse(await _cached_text(request.app), media_type=CONTENT_TYPE)
