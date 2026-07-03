"""Вспомогательная логика админ-роутера: авторизация, валидация regex (ReDoS-гейт),
автоприменение изменений конфига, сериализация ответов. Роутер (router.py) держит
только эндпоинты и импортирует отсюда."""

import datetime as dt
import re
import secrets

import regex as _regex
from fastapi import Header, HTTPException, Request

from backend.config import settings
from backend.entrypoints.detectors.auth import load_api_keys

MAX_REGEX_LEN = 1000

# ReDoS-гейт: состязательные строки, на которых катастрофический бэктрекинг
# (вложенные квантификаторы вида (a+)+, (\d+)+ и т.п.) взрывается. Вариант с
# несовпадающим "хвостом" (…+"!") форсирует полный перебор. Покрывает наиболее
# оружейные семейства; гарантию доступности даёт рантайм-таймаут в
# patterns/base.py (он ловит и то, что гейт пропустил, и правила из БД).
_REDOS_PROBES = [
    "a" * 40,
    "a" * 40 + "!",
    "0" * 40,
    "0" * 40 + "!",
    "-" * 40,
    " " * 40,
    "a1" * 30 + "!",
    "aa " * 20 + "!",
    # длинные варианты — ловят формы вида (.*a){N}$, которым мало 40 символов
    "a" * 160 + "!",
    "0" * 160 + "!",
    "a1" * 80 + "!",
]
_REDOS_PROBE_TIMEOUT_SECONDS = 0.05

# period -> (окно, размер бакета таймлайна): гранулярность подобрана так, чтобы
# точек было 12-30 — читаемо и дёшево.
STAT_PERIODS = {
    "1h": (dt.timedelta(hours=1), 300),
    "24h": (dt.timedelta(hours=24), 3600),
    "7d": (dt.timedelta(days=7), 86400),
}


def require_admin(x_admin_token: str = Header(default="")):
    # compare_digest — сравнение за постоянное время (защита от timing-атаки).
    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(401, "invalid admin token")


def db(request: Request):
    return request.app.state.repo


def validate_regex(pattern: str):
    if len(pattern) > MAX_REGEX_LEN:
        raise HTTPException(400, f"regex слишком длинный (> {MAX_REGEX_LEN})")
    try:
        # Компилируем движком `regex` — тем же, что исполняет паттерны на горячем
        # пути (patterns/base.py), чтобы семантика совпадала.
        compiled = _regex.compile(pattern, _regex.IGNORECASE)
    except _regex.error as e:
        raise HTTPException(400, f"невалидный regex: {e}") from e
    # ReDoS-гейт: паттерн не должен «взрываться» на состязательных строках.
    for probe in _REDOS_PROBES:
        try:
            for _ in compiled.finditer(probe, timeout=_REDOS_PROBE_TIMEOUT_SECONDS):
                pass
        except TimeoutError as e:
            raise HTTPException(
                400,
                "regex отклонён: возможен катастрофический бэктрекинг "
                "(паттерн слишком медленный на состязательном вводе)",
            ) from e


def bump_and_reload(request: Request):
    """Авто-применение: bump версии конфига + немедленный reload движка на этом
    воркере. Остальные воркеры подхватят на ближайшем тике version-поллера."""
    db(request).version.bump_version()
    request.app.state.guard.reload()


def refresh_keys(request: Request):
    """Обновить кэш API-ключей на этом воркере сразу после правки.
    Остальные воркеры подхватят изменения на ближайшем тике поллера."""
    request.app.state.api_keys = load_api_keys(db(request).api_keys)


def safe_filename(name: str) -> str:
    """Имя словаря -> безопасное имя файла для Content-Disposition."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "dict"


# --- сериализаторы ответов --------------------------------------------------
def pii_out(r) -> dict:
    return {"id": r.id, "type": r.type, "regex": r.regex, "enabled": r.enabled}


def nsfw_out(d) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "enabled": d.enabled,
        "word_count": len(d.text.split()),
    }


def relevant_out(c) -> dict:
    return {"id": c.id, "type": c.type, "text": c.text, "enabled": c.enabled}


def key_out(k) -> dict:
    """Безопасное представление ключа: сам ключ не отдаём, только prefix."""
    return {
        "id": k.id,
        "name": k.name,
        "prefix": k.prefix,
        "enabled": k.enabled,
        "created_at": k.created_at.isoformat(),
        "rate_limit_per_min": getattr(k, "rate_limit_per_min", None),
    }


def log_out(r) -> dict:
    return {
        "id": r.id,
        "ts": r.created_at.isoformat(),
        "module": r.module,
        "input": r.input_text,
        "output": r.output,
        "duration_ms": round(r.duration_ms, 3),
        "meta": r.meta,
    }
