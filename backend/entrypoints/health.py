"""Пробы для оркестратора (Kubernetes) и отладки.

Три ручки с разным смыслом — их нельзя путать:

  GET /live    liveness — «процесс не завис?». Тупая и дешёвая: только отвечает.
               Провал -> Kubernetes ПЕРЕЗАПУСКАЕТ под. Поэтому НЕ проверяет БД:
               иначе моргание Postgres увело бы кубер в перезапуск здоровых подов.

  GET /ready   readiness — «готов принимать трафик?». Проверяет зависимости
               (Postgres + Redis). Провал -> под УБИРАЮТ из балансировки (без
               рестарта), трафик идёт на другие; выздоровел — вернут.

  GET /health  человекочитаемый статус с детализацией по зависимостям (для
               curl/дашборда). По готовности совпадает с /ready: 503, если что-то
               лежит.

Проверки блокирующие (psycopg2 SELECT 1, redis ping) — выполняем в threadpool,
чтобы не вешать event loop.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

router = APIRouter()


def _check(fn) -> bool:
    """Прогнать проверку зависимости; любое исключение = «лежит»."""
    try:
        return bool(fn())
    except Exception:
        return False


def _dependencies(app) -> dict[str, bool]:
    """Синхронные проверки зависимостей (вызывать в threadpool)."""
    return {
        "postgres": _check(app.state.repo.ping),
        "redis": _check(app.state.store.ping),
    }


@router.get("/live")
async def live():
    """Liveness: процесс жив и обслуживает запросы. Ничего не проверяем."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    """Readiness: готовность зависимостей. 503, если хоть одна недоступна."""
    checks = await run_in_threadpool(_dependencies, request.app)
    if all(checks.values()):
        return {"status": "ready"}
    return JSONResponse({"status": "not ready", "checks": checks}, status_code=503)


@router.get("/health")
async def health(request: Request):
    """Детальный статус по зависимостям (для людей/отладки)."""
    checks = await run_in_threadpool(_dependencies, request.app)
    ok = all(checks.values())
    body = {
        "status": "ok" if ok else "degraded",
        "checks": {name: "ok" if up else "down" for name, up in checks.items()},
    }
    return JSONResponse(body, status_code=200 if ok else 503)
